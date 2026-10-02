"""Every admin route must refuse anonymous callers. Routes are enumerated from the
app, so new endpoints are covered automatically."""

import re

from app.main import app

PUBLIC = {"/health", "/auth/login", "/auth/logout"}


def admin_routes():
    # The OpenAPI schema lists every API route, however routers are nested.
    for path, ops in app.openapi()["paths"].items():
        if path in PUBLIC or path.startswith("/webhook/"):
            continue
        for method in ops:
            yield method.upper(), re.sub(r"\{[^}]+\}", "1", path)


async def test_there_are_admin_routes():
    assert len(list(admin_routes())) > 10


async def test_all_admin_routes_require_auth(client):
    failures = []
    for method, path in admin_routes():
        r = await client.request(method, path, json={})
        if r.status_code != 401:
            failures.append((method, path, r.status_code))
    assert not failures, failures

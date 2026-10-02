"""Embedding via fastembed (ONNX on CPU, no PyTorch).

Onti Erlani Hub changes (vendored from thesis-rag):
- the model is configurable (EMBED_MODEL) and defaults to the multilingual
  intfloat/multilingual-e5-small, which fastembed doesn't ship: it is registered
  below as a custom model from the official ONNX export on Hugging Face;
- E5 expects "query: " / "passage: " prefixes, so passages get
  settings.passage_prefix as well (queries already had query_instruction).

fastembed's query_embed()/passage_embed() add no prefixes themselves (checked in
fastembed/text/text_embedding_base.py), so both are prepended here.
"""

from collections.abc import Iterable
from functools import lru_cache

import numpy as np
from fastembed import TextEmbedding

from rag.config import settings

# Models fastembed doesn't list natively: name -> add_custom_model kwargs.
CUSTOM_MODELS = {
    "intfloat/multilingual-e5-small": {
        "dim": 384,
        "hf": "intfloat/multilingual-e5-small",
        "model_file": "onnx/model.onnx",
    },
}


def _register_custom(name: str) -> None:
    spec = CUSTOM_MODELS.get(name)
    if spec is None:
        return
    supported = {m["model"] for m in TextEmbedding.list_supported_models()}
    if name in supported:
        return
    from fastembed.common.model_description import ModelSource, PoolingType

    TextEmbedding.add_custom_model(
        model=name,
        pooling=PoolingType.MEAN,
        normalization=True,
        sources=ModelSource(hf=spec["hf"]),
        dim=spec["dim"],
        model_file=spec["model_file"],
    )


@lru_cache(maxsize=1)
def model() -> TextEmbedding:
    _register_custom(settings.embed_model)
    return TextEmbedding(settings.embed_model)


def _normalise(v: np.ndarray) -> np.ndarray:
    # Unit vectors: cosine distance == 1 - dot product, and the index stores them as-is.
    return (v / np.linalg.norm(v, axis=-1, keepdims=True)).astype(np.float32)


def embed_passages(texts: Iterable[str], batch_size: int = 32) -> np.ndarray:
    texts = [settings.passage_prefix + t for t in texts]
    return _normalise(np.array(list(model().passage_embed(texts, batch_size=batch_size))))


def embed_query(query: str) -> np.ndarray:
    return _embed_query(settings.query_instruction + query).copy()


@lru_cache(maxsize=2048)
def _embed_query(text: str) -> np.ndarray:
    # Cached: evaluation runs the same questions through several configurations.
    return _normalise(np.array(next(iter(model().query_embed(text)))))


def dim() -> int:
    return int(embed_query("dimension probe").shape[-1])

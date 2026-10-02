"""Which adapter sends for a conversation."""

from app.channels.base import ChannelAdapter
from app.channels.simulator import SimulatorAdapter

_simulator = SimulatorAdapter()


def adapter_for_channel(channel: str) -> ChannelAdapter:
    if channel == "whatsapp":
        from app.channels.whatsapp import WhatsAppAdapter

        return WhatsAppAdapter()
    if channel in ("messenger", "instagram"):
        from app.channels.meta import MetaMessagingAdapter

        return MetaMessagingAdapter(channel)
    raise ValueError(f"no adapter for channel {channel!r}")


def adapter_for(conversation) -> ChannelAdapter:
    if conversation.simulated:
        return _simulator
    return adapter_for_channel(conversation.channel)

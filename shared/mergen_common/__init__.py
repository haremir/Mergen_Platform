# mergen_common — Zero-dependency shared primitives for the Mergen Platform.
# All packages in this monorepo may import from here, but this package itself
# MUST NOT import from any other internal package or third-party library.
# Only the Python standard library is permitted.
from mergen_common.models import (
    InboundMessage,
    OutboundMessage,
    Tenant,
    KnowledgeField,
)

__all__ = [
    "InboundMessage",
    "OutboundMessage",
    "Tenant",
    "KnowledgeField",
]

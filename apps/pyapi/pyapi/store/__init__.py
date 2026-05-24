from .engine import normalize_url, shared_engine
from .errors import NotFoundError
from .ids import new_id
from .models import MessageRecord, SessionRecord
from .store import Store

# Register MemoryRecord with SQLModel.metadata so create_tables=True picks it up.
# Import is for side-effect only; the symbol itself is re-exported from pyapi.memory.
from pyapi.memory.models import MemoryRecord as _MemoryRecord  # noqa: F401

__all__ = [
    "MessageRecord",
    "NotFoundError",
    "SessionRecord",
    "Store",
    "new_id",
    "normalize_url",
    "shared_engine",
]

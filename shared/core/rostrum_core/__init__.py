"""rostrum_core: the shared Python core of every Rostrum app (contract: ../OPERATIONS.md).

Documents of items with stable ids, one registry of operations, one door in (`Document.apply`), one history
(undo / redo per author, a drag is one step, named versions, who changed what), and the script re-run merge
that never wipes a person's work.
"""
from .document import Document, Event
from .errors import RostrumError, codes, did_you_mean
from .history import Change
from .kind import DocKind
from .merge import MergeReport
from .params import Param
from .registry import PLUGIN_ITEM, Operation, Registry
from .who import Who

__all__ = ["PLUGIN_ITEM", "Change", "DocKind", "Document", "Event", "MergeReport", "Operation", "Param", "Registry",
           "RostrumError", "Who", "codes", "did_you_mean"]

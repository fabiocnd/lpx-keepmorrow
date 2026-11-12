"""Resource boundaries shared by source and persisted document formats."""

from .json_document import check_json_budget

__all__ = ["check_json_budget"]

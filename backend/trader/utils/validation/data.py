from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .task import get_stock_preparer


get_stock_validator = get_stock_preparer

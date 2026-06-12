from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .status import is_stock_data_ready


is_stock_valid = is_stock_data_ready

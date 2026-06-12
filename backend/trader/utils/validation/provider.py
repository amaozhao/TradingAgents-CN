from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .route import prepare_stock_data


validate_stock_exists = prepare_stock_data

from typing import Any, Optional

from pydantic import BaseModel


class ApiResponse(BaseModel):
    """统一API响应模型，匹配 app.core.response.ok/fail 的返回结构。"""

    success: bool
    data: Any = None
    message: str
    timestamp: Optional[str] = None
    code: Optional[int] = None

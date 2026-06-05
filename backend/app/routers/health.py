import time
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthData(BaseModel):
    status: str
    version: str
    timestamp: int
    service: str


class HealthResponse(BaseModel):
    success: bool
    data: HealthData
    message: str


class HealthzResponse(BaseModel):
    status: str


class ReadyzResponse(BaseModel):
    ready: bool


def get_version() -> str:
    """从 VERSION 文件读取版本号"""
    try:
        for root in (
            Path(__file__).resolve().parents[3],
            Path(__file__).resolve().parents[2],
        ):
            version_file = root / "VERSION"
            if version_file.exists():
                return version_file.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return "0.1.16"  # 默认版本号


@router.get("/health", response_model=HealthResponse)
async def health():
    """健康检查接口 - 前端使用"""
    return {
        "success": True,
        "data": {
            "status": "ok",
            "version": get_version(),
            "timestamp": int(time.time()),
            "service": "AGENTrader API",
        },
        "message": "服务运行正常",
    }


@router.get("/healthz", response_model=HealthzResponse)
async def healthz():
    """Kubernetes健康检查"""
    return {"status": "ok"}


@router.get("/readyz", response_model=ReadyzResponse)
async def readyz():
    """Kubernetes就绪检查"""
    return {"ready": True}

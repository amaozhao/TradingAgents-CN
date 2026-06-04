from .common import Path
from .service import ConfigManager
from .tracker import TokenTracker


# 全局配置管理器实例 - 使用项目根目录的配置
def _get_project_config_dir():
    """获取项目根目录的配置目录"""
    # 从当前文件位置推断项目根目录
    current_file = Path(__file__)  # trader/config/manager/runtime.py
    project_root = current_file.resolve().parents[
        4
    ]  # backend/trader/config/manager -> 仓库根目录
    return str(project_root / "config")


config_manager = ConfigManager(_get_project_config_dir())
token_tracker = TokenTracker(config_manager)

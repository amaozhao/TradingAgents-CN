"""
侧边栏组件
"""

import logging
from support.path import REPO_ROOT

logger = logging.getLogger(__name__)
project_root = REPO_ROOT


def get_version():
    """从VERSION文件读取项目版本号"""
    try:
        version_file = project_root / "VERSION"
        if version_file.exists():
            return version_file.read_text().strip()
        else:
            return "unknown"
    except Exception as e:
        logger.warning(f"无法读取版本文件: {e}")
        return "unknown"

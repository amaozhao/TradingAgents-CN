from .base import BaseConfigMixin
from .catalog import ModelCatalogMixin
from .database import DatabaseConfigMixin
from .grouping import DataSourceGroupingMixin
from .market import MarketCategoryMixin
from .models import ProviderModelMixin
from .provider import LLMProviderMixin
from .settings import SettingsMixin
from .system import SystemConfigMixin
from .testing.compatible import CompatibleApiTestMixin
from .testing.database import DatabaseConfigTestMixin
from .testing.llm import LLMConfigTestMixin
from .testing.provider import ProviderApiTestMixin
from .testing.source import DataSourceConfigTestMixin


class ConfigService(
    BaseConfigMixin,
    MarketCategoryMixin,
    DataSourceGroupingMixin,
    SystemConfigMixin,
    SettingsMixin,
    LLMConfigTestMixin,
    DataSourceConfigTestMixin,
    DatabaseConfigTestMixin,
    DatabaseConfigMixin,
    ModelCatalogMixin,
    LLMProviderMixin,
    ProviderApiTestMixin,
    ProviderModelMixin,
    CompatibleApiTestMixin,
):
    """配置管理服务类"""


config_service = ConfigService()

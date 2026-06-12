import importlib.util
import unittest
from pathlib import Path


def load_providers_module():
    module_path = Path(__file__).resolve().parents[5] / "trader" / "llm" / "clients" / "providers.py"
    spec = importlib.util.spec_from_file_location(
        "trader_llm_clients_providers_under_test",
        module_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


providers_module = load_providers_module()
canonical_aliases = providers_module.canonical_aliases
default_backend_url = providers_module.default_backend_url
env_key_for_provider = providers_module.env_key_for_provider
normalize_provider_key = providers_module.normalize_provider_key


class ProviderKeysTests(unittest.TestCase):
    def test_normalize_dashscope_to_qwen(self):
        self.assertEqual(normalize_provider_key("dashscope"), "qwen")
        self.assertEqual(normalize_provider_key("阿里百炼"), "qwen")

    def test_normalize_zhipu_to_glm(self):
        self.assertEqual(normalize_provider_key("zhipu"), "glm")
        self.assertEqual(normalize_provider_key("智谱AI"), "glm")

    def test_env_key_mapping(self):
        self.assertEqual(env_key_for_provider("qwen"), "DASHSCOPE_API_KEY")
        self.assertEqual(env_key_for_provider("dashscope"), "DASHSCOPE_API_KEY")
        self.assertEqual(env_key_for_provider("glm"), "ZHIPU_API_KEY")
        self.assertEqual(
            env_key_for_provider("minimax-token-plan"),
            "MINIMAX_TOKEN_PLAN_API_KEY",
        )

    def test_default_backend_url_mapping(self):
        self.assertIn("dashscope.aliyuncs.com", default_backend_url("qwen"))
        self.assertIn("open.bigmodel.cn", default_backend_url("glm"))
        self.assertEqual(
            default_backend_url("minimax-token-plan"),
            "https://api.minimaxi.com/anthropic",
        )

    def test_canonical_aliases(self):
        self.assertIn("dashscope", canonical_aliases("qwen"))
        self.assertIn("zhipu", canonical_aliases("glm"))


if __name__ == "__main__":
    unittest.main()

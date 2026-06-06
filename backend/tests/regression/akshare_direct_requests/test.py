from types import SimpleNamespace

from trader.flows.providers.china import akshare as akshare_module


def test_akshare_requests_ignore_environment_proxy(monkeypatch):
    calls = []

    class FakeResponse:
        status_code = 200
        text = "{}"

    class FakeSession:
        trust_env = True

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get(self, url, **kwargs):
            calls.append(
                {
                    "url": url,
                    "kwargs": kwargs,
                    "trust_env": self.trust_env,
                }
            )
            return FakeResponse()

    class FakeRequests:
        def get(self, *_args, **_kwargs):
            raise AssertionError("patched get should use a trust_env=False session")

        def Session(self):
            return FakeSession()

    fake_requests = FakeRequests()
    original_import_module = akshare_module.importlib.import_module

    def fake_import_module(name):
        if name == "akshare":
            return SimpleNamespace()
        if name == "requests":
            return fake_requests
        if name == "curl_cffi":
            raise ImportError("curl_cffi intentionally unavailable")
        return original_import_module(name)

    monkeypatch.setattr(akshare_module.importlib, "import_module", fake_import_module)

    akshare_module.AKShareProvider()
    fake_requests.get("https://push2his.eastmoney.com/api/qt/stock/kline/get")

    assert calls
    assert calls[0]["trust_env"] is False
    assert calls[0]["kwargs"]["proxies"] == {}


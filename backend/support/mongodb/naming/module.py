import importlib
import os
import unittest


class MongoDbNamingTests(unittest.TestCase):
    def test_auto_scope_debug_uses_major_instance(self):
        Settings = getattr(importlib.import_module('app.core.config'), 'Settings')

        env = {
            "DEBUG": "true",
            "MONGODB_DATABASE": "trading_agents_cn",
            "MONGODB_DATABASE_SCOPE": "auto",
            "TRADING_AGENTS_VERSION": "1.2.3",
            "MONGODB_DATABASE_INSTANCE": "devx",
        }

        old = {k: os.environ.get(k) for k in env}
        try:
            os.environ.update(env)
            s = Settings()
            self.assertEqual(s.mongo_db, "trading_agents_cn_v1_devx")
            identity = s.mongo_db_identity
            self.assertEqual(identity["scope_effective"], "major_instance")
            self.assertEqual(identity["major_version"], "1")
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_auto_scope_prod_uses_explicit(self):
        Settings = getattr(importlib.import_module('app.core.config'), 'Settings')

        env = {
            "DEBUG": "false",
            "MONGODB_DATABASE": "trading_agents_cn",
            "MONGODB_DATABASE_SCOPE": "auto",
            "TRADING_AGENTS_VERSION": "9.0.0",
        }

        old = {k: os.environ.get(k) for k in env}
        try:
            os.environ.update(env)
            s = Settings()
            self.assertEqual(s.mongo_db, "trading_agents_cn")
            identity = s.mongo_db_identity
            self.assertEqual(identity["scope_effective"], "explicit")
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_debug_shared_db_requires_explicit_override(self):
        Settings = getattr(importlib.import_module('app.core.config'), 'Settings')

        env = {
            "DEBUG": "true",
            "MONGODB_DATABASE": "trading_agents_cn",
            "MONGODB_DATABASE_SCOPE": "explicit",
            "ALLOW_SHARED_DB_IN_DEBUG": "false",
        }

        old = {k: os.environ.get(k) for k in env}
        try:
            os.environ.update(env)
            s = Settings()
            self.assertEqual(s.mongo_db_identity["scope_effective"], "explicit")
            self.assertFalse(s.ALLOW_SHARED_DB_IN_DEBUG)
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


if __name__ == "__main__":
    unittest.main()

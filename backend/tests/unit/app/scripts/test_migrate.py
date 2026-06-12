from support.registry import export_module as _export_module

_export_module(globals(), "support.migrate.postgres.script.module")
del _export_module

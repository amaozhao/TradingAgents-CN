from importlib import import_module as _import_module
import sys as _sys

_module = _import_module(".core", __package__)
_sys.modules[__name__] = _module
globals().update(_module.__dict__)
del _import_module, _sys, _module

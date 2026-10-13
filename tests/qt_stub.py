# -*- coding: utf-8 -*-
"""بديل خفيف لـ PySide6 لاستيراد adhkar_app.py في بيئة بلا Qt واختبار دوالّه غير الرسومية فقط.

هذا ليس اختبارًا للواجهة: الأصناف الرسومية لا تُنفَّذ هنا.
"""
import sys
import types


class _Meta(type):
    def __getattr__(cls, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _Any()

    def __or__(cls, other):
        return _Any()


class _Any(metaclass=_Meta):
    def __init__(self, *a, **k):
        pass

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _Any()

    def __call__(self, *a, **k):
        return _Any()

    def __or__(self, other):
        return _Any()

    __ror__ = __and__ = __rand__ = __or__

    def __iter__(self):
        return iter(())


def install():
    if "PySide6" in sys.modules and getattr(sys.modules["PySide6"], "_is_stub", False):
        return
    cache = {}

    def make_module(name):
        mod = types.ModuleType(name)
        mod.__path__ = []
        mod._is_stub = True

        def __getattr__(attr):
            if attr.startswith("__"):
                raise AttributeError(attr)
            if attr not in cache:
                cache[attr] = type(attr, (_Any,), {})
            return cache[attr]

        mod.__getattr__ = __getattr__
        return mod

    for n in ("PySide6", "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets"):
        sys.modules[n] = make_module(n)

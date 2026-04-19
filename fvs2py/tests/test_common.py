"""Unit tests for helpers in :mod:`fvs2py.common`.

These tests exercise the descriptor protocol of :class:`fvs2py.common.fvs_property`
without loading the real FVS shared library. A sentinel ``_StubLib`` class stands
in for the attribute the guard checks, so the descriptor behaves as it would on
a fully-initialized :class:`fvs2py.FVS` instance.
"""

from __future__ import annotations

import pytest

from fvs2py.common import fvs_property


class _StubLib:
    """Sentinel `_lib` attribute used by `fvs_property` loaded-library checks."""


class _Holder:
    """Minimal host exercising the descriptor under test.

    Declared as a module-level class rather than a nested class so the
    descriptor binds to a stable owner across every test function.
    """

    def __init__(self, value: int = 0) -> None:
        self._lib: _StubLib | None = _StubLib()
        self._value = value

    @fvs_property
    def value(self) -> int:
        return self._value

    @value.setter  # type: ignore[no-redef]
    def value(self, new_value: int) -> None:
        self._value = new_value

    @fvs_property
    def read_only(self) -> int:
        return self._value


def test_fvs_property_getter_returns_value_when_library_loaded():
    holder = _Holder(value=7)
    assert holder.value == 7


def test_fvs_property_setter_updates_value():
    holder = _Holder(value=0)
    holder.value = 42
    assert holder.value == 42
    assert holder._value == 42


def test_fvs_property_getter_raises_when_library_missing():
    holder = _Holder(value=3)
    holder._lib = None
    with pytest.raises(
        RuntimeError,
        match="FVS library not loaded, unable to access value property.",
    ):
        holder.value


def test_fvs_property_setter_raises_when_library_missing():
    holder = _Holder(value=0)
    holder._lib = None
    with pytest.raises(
        RuntimeError,
        match="FVS library not loaded, unable to set value property.",
    ):
        holder.value = 1


def test_fvs_property_without_setter_rejects_assignment():
    holder = _Holder(value=0)
    with pytest.raises(AttributeError, match="has no setter"):
        holder.read_only = 5


def test_fvs_property_class_access_returns_descriptor():
    descriptor = _Holder.value
    assert isinstance(descriptor, fvs_property)
    assert descriptor.__name__ == "value"


def test_fvs_property_preserves_getter_docstring():
    def getter(_self: object) -> int:
        """Custom docstring."""
        return 0

    descriptor = fvs_property(getter)
    assert descriptor.__doc__ == "Custom docstring."


def test_fvs_property_setter_builds_new_descriptor_with_same_getter():
    def getter(_self: object) -> int:
        return 1

    def setter(_self: object, _value: int) -> None:
        return None

    base = fvs_property(getter)
    with_setter = base.setter(setter)
    assert with_setter is not base
    assert with_setter.fget is base.fget
    assert with_setter.fset is setter

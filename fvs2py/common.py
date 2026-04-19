from __future__ import annotations

import ctypes as ct
import functools
import logging
import os
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar, cast

P = ParamSpec("P")
T = TypeVar("T")
ClassT = TypeVar("ClassT", bound=type)


def load_dll(dll_path: str | os.PathLike) -> ct.CDLL:
    """Loads a Dynamic Link Library.

    Supports linux shared objects, not Windows DLLs.

    Args:
        dll_path (str | os.PathLike): the path to the DLL
            to be loaded.

    Returns:
        the loaded DLL as a ctypes CDLL instance
    """
    dll_path_str = os.fspath(dll_path)
    logging.info(f"Loading library from {dll_path_str}")
    dll = ct.CDLL(dll_path_str)
    logging.info(f"Library loaded successfully from {dll_path_str}")
    return dll


def unload_dll(dll: ct.CDLL) -> None:
    """Unloads a Dynamic Link Library.

    Args:
        dll: the loaded DLL.
    """
    close_func = dll.dlclose
    close_func.argtypes = (ct.c_void_p,)
    close_func.restype = ct.c_int
    result = close_func(dll._handle)
    if result != 0:
        msg = f"Failed to unload DLL: {result}"
        raise RuntimeError(msg)
    logging.debug("Library unloaded successfully.")


def function_requires_fvs_library() -> Callable[
    [Callable[P, T]], Callable[P, T]
]:
    """Decorator ensuring a ._lib attribute is present and not None.

    This decorator is intended to be applied to instance methods that rely upon
    accessing attributes or routines frome the FVS library. If the FVS library has been
    unloaded without this protection, a segmentation fault would occur.
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs) -> T:
            if not hasattr(self, "_lib") or self._lib is None:
                msg = f"FVS library not loaded, unable to call {func.__name__}."
                raise RuntimeError(msg)
            return func(self, *args, **kwargs)

        return cast(Callable[P, T], wrapper)

    return decorator


def fvs_property(func: Callable[..., T]) -> property:
    """A property decorator that checks if the FVS library is loaded before accessing.

    This combines @property with a check for self._lib. This decorator will help ensure
    that the FVS library is loaded before accessing the property. If the FVS library
    has been unloaded without this protection, a segmentation fault would occur.

    Args:
        func: The property getter function to wrap.

    Returns:
        A property descriptor with FVS library checking.
    """

    @functools.wraps(func)
    def wrapper(self) -> T:
        if not hasattr(self, "_lib") or self._lib is None:
            msg = f"FVS library not loaded, unable to access {func.__name__} property."
            raise RuntimeError(msg)
        return func(self)

    return property(wrapper)


def no_fvs_library_required(func: Callable[P, T]) -> Callable[P, T]:
    """Mark a method so `class_requires_fvs_library` leaves it unwrapped.

    Use this to opt a pure-Python helper out of the automatic ``_lib``-loaded
    guard applied by :func:`class_requires_fvs_library`. The marker is read
    from the underlying function object during class decoration.

    Args:
        func: Instance method to leave unguarded.

    Returns:
        The same function object with a ``_fvs_library_required`` attribute set
        to ``False``.
    """
    func._fvs_library_required = False  # type: ignore[attr-defined]
    return func


def class_requires_fvs_library(cls: ClassT) -> ClassT:
    """Decorator enforcing `function_requires_fvs_library` for all public methods.

    Walks ``cls.__mro__`` so that public methods contributed by mixins receive
    the same ``_lib``-loaded guard that methods defined directly on ``cls``
    get. The first occurrence of each public name wins (respecting MRO), so
    overrides on ``cls`` are not shadowed by same-named methods on a base.

    Skips:
      - names that start with ``_`` (private / dunder).
      - non-callables (e.g. ``property`` descriptors, which are expected to
        carry their own guard via :func:`fvs_property`).
      - ``staticmethod`` / ``classmethod`` descriptors — they have no ``self``
        to inspect and their own guard would have to be different.
      - methods marked with :func:`no_fvs_library_required`.
      - methods already wrapped by a previous call (idempotent).

    Args:
        cls: The class to decorate.

    Returns:
        The same class, with public methods replaced by ``_lib``-guarded
        wrappers.
    """
    wrapped_names: set[str] = set()
    for base in cls.__mro__:
        if base is object:
            continue
        for name, method in vars(base).items():
            if name in wrapped_names:
                continue
            if name.startswith("_") or not callable(method):
                continue
            if isinstance(method, (staticmethod, classmethod)):
                continue
            if getattr(method, "_fvs_library_required", True) is False:
                continue
            if getattr(method, "_fvs_wrapped", False):
                continue
            wrapped = function_requires_fvs_library()(method)
            wrapped._fvs_wrapped = True  # type: ignore[attr-defined]
            setattr(cls, name, wrapped)
            wrapped_names.add(name)
    return cls


def call_out(
    func: Callable[..., Any],
    *in_args: Any,
    out_types: tuple[type, ...] = (ct.c_int,),
) -> Any:
    """Call a ctypes function, auto-allocating output pointer args.

    Allocates one fresh ctypes object of each type in ``out_types``, appends
    them (in order) after ``in_args`` when calling ``func``, and returns the
    unwrapped ``.value`` of each output.

    Args:
        func: Resolved ctypes foreign function whose trailing parameters are
            ``POINTER`` types corresponding to ``out_types``.
        *in_args: Positional input arguments passed to ``func`` unchanged.
        out_types: Ctypes scalar types to allocate as output parameters.
            Defaults to a single ``ct.c_int`` output.

    Returns:
        The scalar value if exactly one output was requested, otherwise a
        tuple of unwrapped scalars in declaration order.
    """
    outs = [t(0) for t in out_types]
    func(*in_args, *outs)
    if len(outs) == 1:
        return outs[0].value
    return tuple(o.value for o in outs)

"""Declarative registry of FVS routine signatures + a thin invoker.

Each FVS routine is described by a :class:`Routine` whose parameters are
:class:`Param` records carrying a name, a ctypes type (static or a runtime
factory closure over the call kwargs), and an :class:`Intent` flag indicating
direction. :class:`Routine.call` resolves dynamic types, auto-allocates
output buffers, assigns ``argtypes``/``restype`` on the resolved foreign
function, invokes it, and dispatches any configured return-code policy.

Mixin methods own Python-facing ergonomics and derive dependent args (e.g.
``nattr = len(attr)``, ``ntrees = len(values)``) before handing a
fully-specified kwarg dict to :meth:`FvsCore._invoke`. The registry itself
stays free of derivation or validation logic.

This module ships the scaffolding only: the :data:`FVS_ROUTINES` mapping
starts empty and is populated by subsequent PRs as each mixin migrates to
the invoker.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from enum import Flag, auto
from types import MappingProxyType
from typing import Any

import numpy as np

from fvs2py._constants import STR_C_CONTIGUOUS
from fvs2py.enums import FvsAttrReturnCode


class Intent(Flag):
    """Direction flag for a :class:`Param`.

    ``IN`` parameters are supplied by callers as kwargs and passed through to
    the foreign function unchanged. ``OUT`` parameters are auto-allocated by
    the invoker and returned to the caller; callers must not pass them.
    ``INOUT`` (``IN | OUT``) parameters are caller-owned buffers that the
    foreign function may read from and write into in place.
    """

    IN = auto()
    OUT = auto()
    INOUT = IN | OUT


Scope = Mapping[str, Any]
ParamType = type | Callable[[Scope], type]


@dataclass(frozen=True, slots=True, kw_only=True)
class Param:
    """One parameter in an FVS routine's signature.

    Attributes:
        name: Kwarg name used by :meth:`Routine.call`.
        ctype: Either a ctypes type (static) or a callable that receives the
            call-site kwargs as scope and returns a concrete ctypes type.
            Factories are typically closures produced by :func:`ndptr_f64` or
            :func:`ndptr_intc`.
        intent: Direction flag; see :class:`Intent`.
    """

    name: str
    ctype: ParamType
    intent: Intent = Intent.IN


@dataclass(frozen=True, slots=True, kw_only=True)
class Routine:
    """Declarative description of an FVS routine's ctypes interface.

    Attributes:
        params: Parameters in Fortran declaration order.
        restype: Ctypes return type, or ``None`` if the routine returns
            nothing (the usual case for FVS subroutines).
        rc_param: Name of the return-code OUT parameter, or ``None`` if the
            routine does not report a return code.
        rc_policy: Callable invoked with the return-code integer after a
            successful call; should raise on error and return ``None`` on OK.
        name: Routine identifier used in error messages. Populated from the
            :data:`FVS_ROUTINES` mapping key; construction-site entries may
            leave it empty.
    """

    params: tuple[Param, ...]
    restype: type | None = None
    rc_param: str | None = "rtncode"
    rc_policy: Callable[[int], None] | None = None
    name: str = ""

    def __post_init__(self) -> None:
        """Validate the declarative shape at construction time.

        Catches structural misconfigurations that would otherwise surface as
        silently-skipped return-code validation at call time: declaring an
        :attr:`rc_policy` without an :attr:`rc_param`, or pointing
        :attr:`rc_param` at a name that isn't a declared :class:`Intent.OUT`
        parameter. Return codes are write-only by convention, so ``INOUT``
        and ``IN`` params are rejected as ``rc_param`` targets.
        """
        if self.rc_policy is None:
            return
        if self.rc_param is None:
            msg = f"{self._label()}: rc_policy requires rc_param"
            raise ValueError(msg)
        out_names = {p.name for p in self.params if p.intent == Intent.OUT}
        if self.rc_param not in out_names:
            msg = (
                f"{self._label()}: rc_param {self.rc_param!r} must name an "
                f"Intent.OUT param; OUT params are {sorted(out_names)}"
            )
            raise ValueError(msg)

    def call(self, func: Any, /, **kwargs: Any) -> Any:
        """Dispatch a call to ``func`` using this routine's declarative shape.

        Resolves any dynamic-type factories against ``kwargs``, auto-allocates
        OUT buffers, assigns ``argtypes``/``restype`` on ``func``, invokes it
        with positional args in declaration order, runs the configured return
        code policy (if any), and returns the OUT values.

        Args:
            func: Resolved foreign function (ctypes ``_FuncPointer``) or a
                Python callable compatible with the routine's call shape (used
                by tests).
            **kwargs: One entry per non-OUT parameter.

        Returns:
            ``None`` if the routine has no non-rc OUT params, the unwrapped
            scalar value if it has exactly one, or a ``dict[name, value]`` if
            it has several.

        Raises:
            TypeError: If required kwargs are missing, unknown kwargs are
                supplied, or an OUT-only param is passed by the caller.
        """
        param_names = {p.name for p in self.params}
        expected_inputs = {
            p.name for p in self.params if p.intent != Intent.OUT
        }
        provided = set(kwargs)

        missing = expected_inputs - provided
        if missing:
            msg = f"{self._label()}: missing required kwargs {sorted(missing)}"
            raise TypeError(msg)

        unknown = provided - param_names
        if unknown:
            msg = f"{self._label()}: unknown kwargs {sorted(unknown)}"
            raise TypeError(msg)

        out_in_kwargs = provided & {
            p.name for p in self.params if p.intent == Intent.OUT
        }
        if out_in_kwargs:
            msg = (
                f"{self._label()}: OUT params must not be provided by the "
                f"caller: {sorted(out_in_kwargs)}"
            )
            raise TypeError(msg)

        argtypes: list[type] = []
        for p in self.params:
            argtypes.append(_resolve_ctype(p.ctype, kwargs))

        out_bufs: dict[str, Any] = {}
        call_args: list[Any] = []
        for p, t in zip(self.params, argtypes, strict=True):
            if p.intent == Intent.OUT:
                inner = getattr(t, "_type_", None)
                if inner is None:
                    msg = (
                        f"{self._label()}: OUT param {p.name!r} has ctype "
                        f"{t!r} which is not a pointer-like type; cannot "
                        f"auto-allocate."
                    )
                    raise TypeError(msg)
                buf = inner()
                out_bufs[p.name] = buf
                call_args.append(buf)
            else:
                call_args.append(kwargs[p.name])

        func.argtypes = argtypes
        func.restype = self.restype
        func(*call_args)

        if self.rc_policy is not None and self.rc_param is not None:
            self.rc_policy(out_bufs[self.rc_param].value)

        non_rc = {k: v for k, v in out_bufs.items() if k != self.rc_param}
        if not non_rc:
            return None
        if len(non_rc) == 1:
            return next(iter(non_rc.values())).value
        return {k: v.value for k, v in non_rc.items()}

    def _label(self) -> str:
        """Return a short identifier for error messages.

        Prefers the registry-populated :attr:`name` when present; falls back
        to a generic ``Routine(...)`` tag for routines constructed outside
        the registry (e.g. in unit tests).
        """
        return self.name or "Routine"


def _resolve_ctype(ctype: ParamType, scope: Scope) -> type:
    """Return a concrete ctypes type, invoking ``ctype`` if it's a factory.

    Static types (classes like ``ct.c_int`` or an ``ndpointer`` subclass
    produced by :func:`numpy.ctypeslib.ndpointer`) are returned unchanged.
    Callables that are not types are invoked with ``scope`` and expected to
    return a ctypes type.
    """
    if isinstance(ctype, type):
        return ctype
    return ctype(scope)


def _unwrap(v: Any) -> int:
    """Return the integer value of ``v``.

    Accepts either a plain int or a ctypes scalar with a ``.value``
    attribute. Mixin methods sometimes have a dimension as a bare Python int
    (``dims[STR_NTREES]``) and sometimes as a ctypes scalar
    (``self._ntrees``). :func:`ndptr_f64` and :func:`ndptr_intc` factories
    call through this helper so either form is accepted at the call site.
    """
    return v.value if hasattr(v, "value") else int(v)


def ndptr_f64(
    *dim_keys: str, flags: str = STR_C_CONTIGUOUS
) -> Callable[[Scope], type]:
    """Build a factory that resolves a contiguous ``float64`` ndpointer.

    The returned factory reads each ``dim_keys`` entry from the call scope
    (kwargs), unwraps ctypes scalars via :func:`_unwrap`, and returns an
    ``np.ctypeslib.ndpointer`` subclass with the resolved shape.
    """

    def factory(scope: Scope) -> type:
        shape = tuple(_unwrap(scope[k]) for k in dim_keys)
        return np.ctypeslib.ndpointer(  # type: ignore[return-value]
            np.float64, shape=shape, flags=flags
        )

    return factory


def ndptr_intc(
    *dim_keys: str, flags: str = STR_C_CONTIGUOUS
) -> Callable[[Scope], type]:
    """Build a factory that resolves a contiguous ``intc`` ndpointer.

    See :func:`ndptr_f64` for the shape-resolution semantics; this variant
    targets C-int arrays, as used by ``fvsSummary``.
    """

    def factory(scope: Scope) -> type:
        shape = tuple(_unwrap(scope[k]) for k in dim_keys)
        return np.ctypeslib.ndpointer(  # type: ignore[return-value]
            np.intc, shape=shape, flags=flags
        )

    return factory


def attr_accessor_policy(rc: int) -> None:
    """Raise if ``rc`` is not :attr:`FvsAttrReturnCode.OK`.

    Consumed by the ``rc_policy`` field on :class:`Routine` entries whose
    return codes follow the canonical attr-accessor convention shared by
    ``fvsSpeciesAttr``, ``fvsTreeAttr``, and similar routines. For codes
    outside the known set, a generic :class:`RuntimeError` is raised.
    """
    if rc == FvsAttrReturnCode.OK:
        return
    try:
        member = FvsAttrReturnCode(rc)  # type: ignore[call-arg]
    except ValueError as exc:
        msg = f"unrecognized attribute-accessor return code: {rc}"
        raise RuntimeError(msg) from exc
    if member == FvsAttrReturnCode.NAME_NOT_FOUND:
        raise NameError(member.message)
    raise RuntimeError(member.message)


_RAW_ROUTINES: dict[str, Routine] = {
    # Registry seeds are intentionally empty in this scaffolding commit.
    # Each follow-up PR adds its routine's :class:`Routine` alongside the
    # corresponding mixin migration so every entry lands with a matching
    # call site. Insertion order is the un-mangled FVS routine name; each
    # entry lists its params in Fortran declaration order.
}


FVS_ROUTINES: Mapping[str, Routine] = MappingProxyType(
    {k: replace(v, name=k) for k, v in _RAW_ROUTINES.items()}
)
"""Immutable registry of FVS routine call descriptions.

Keyed by the un-mangled FVS routine name (matching :data:`NEEDED_ROUTINES`).
The registry ships empty in the scaffolding commit; entries are added by
later PRs as each mixin migrates to :meth:`FvsCore._invoke`. Routines not
(yet) described here remain resolvable through :class:`FvsCore` without the
registry applying a signature to them.
"""

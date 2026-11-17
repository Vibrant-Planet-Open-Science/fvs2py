"""Declarative registry of FVS routine signatures + a thin invoker.

Each FVS routine is described by a `Routine` whose parameters are `Param`
records carrying a name, a ctypes type (static or a runtime factory closure over
the call kwargs), and an `out` flag for scalar outputs. `Routine.call` resolves
dynamic types, auto-allocates output buffers, assigns `argtypes`/`restype` on
the resolved foreign function, invokes it, and dispatches any configured
return-code policy.

Callers derive dependent args (e.g. `nch = len(attr)`) before handing a
fully-specified kwarg dict to `FvsCore._invoke`. The registry itself stays free
of derivation or validation logic.
"""

from __future__ import annotations

import ctypes as ct
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any

import numpy as np

from fvs2py.constants import (
    STR_C_CONTIGUOUS,
    STR_MAXCYCLES,
    STR_MAXPLOTS,
    STR_MAXSPECIES,
    STR_MAXTREES,
    STR_MXCWDOBJS,
    STR_MXDEADOBJS,
    STR_MXSVSOBJS,
    STR_NCWDOBJS,
    STR_NCYCLES,
    STR_NDEADOBJS,
    STR_NOBJS,
    STR_NPLOTS,
    STR_NSVSOBJS,
    STR_NTREES,
)
from fvs2py.enums import FvsAttrReturnCode

Scope = Mapping[str, Any]
ParamType = type | Callable[[Scope], type]


@dataclass(frozen=True, slots=True, kw_only=True)
class Param:
    """One parameter in an FVS routine's signature.

    Attributes:
        name: Kwarg name used by `Routine.call`.
        ctype: Either a ctypes type (static) or a callable that receives the
            call-site kwargs as scope and returns a concrete ctypes type.
            Factories are typically closures produced by `ndptr_f64`.
        out: `True` for a scalar output the invoker allocates and returns;
            callers must not pass it. Everything else is passed through from
            kwargs, including buffers FVS writes into in place.
    """

    name: str
    ctype: ParamType
    out: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class Routine:
    """Declarative description of an FVS routine's ctypes interface.

    Attributes:
        params: Parameters in Fortran declaration order.
        restype: Ctypes return type, or `None` if the routine returns nothing
            (the usual case for FVS subroutines).
        rc_param: Name of the return-code OUT parameter, or `None` if the
            routine does not report a return code.
        rc_policy: Callable invoked with the return-code integer after a
            successful call; should raise on error and return `None` on OK.
        name: Routine identifier used in error messages. Populated from the
            `FVS_ROUTINES` mapping key; construction-site entries may leave it
            empty.
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
        `rc_policy` without an `rc_param`, or pointing `rc_param` at a name that
        isn't a declared `out` parameter.
        """
        if self.rc_policy is None:
            return
        if self.rc_param is None:
            msg = f"{self._label()}: rc_policy requires rc_param"
            raise ValueError(msg)
        out_names = {p.name for p in self.params if p.out}
        if self.rc_param not in out_names:
            msg = (
                f"{self._label()}: rc_param {self.rc_param!r} must name an "
                f"OUT param; OUT params are {sorted(out_names)}"
            )
            raise ValueError(msg)

    def call(self, func: Any, /, **kwargs: Any) -> Any:
        """Dispatch a call to `func` using this routine's declarative shape.

        Resolves any dynamic-type factories against `kwargs`, auto-allocates OUT
        buffers, assigns `argtypes`/`restype` on `func`, invokes it with
        positional args in declaration order, runs the configured return code
        policy (if any), and returns the OUT values.

        Args:
            func: Resolved foreign function (ctypes `_FuncPointer`) or a Python
                callable compatible with the routine's call shape (used by
                tests).
            **kwargs: One entry per non-OUT parameter.

        Returns:
            `None` if the routine has no non-rc OUT params, the unwrapped scalar
            value if it has exactly one, or a `dict[name, value]` if it has
            several.

        Raises:
            TypeError: If required kwargs are missing, unknown kwargs are
                supplied, or an OUT-only param is passed by the caller.
        """
        param_names = {p.name for p in self.params}
        expected_inputs = {p.name for p in self.params if not p.out}
        provided = set(kwargs)

        missing = expected_inputs - provided
        if missing:
            msg = f"{self._label()}: missing required kwargs {sorted(missing)}"
            raise TypeError(msg)

        unknown = provided - param_names
        if unknown:
            msg = f"{self._label()}: unknown kwargs {sorted(unknown)}"
            raise TypeError(msg)

        out_in_kwargs = provided & {p.name for p in self.params if p.out}
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
            if p.out:
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

        Prefers the registry-populated `name` when present; falls back to a
        generic `Routine(...)` tag for routines constructed outside the registry
        (e.g. in unit tests).
        """
        return self.name or "Routine"


def _resolve_ctype(ctype: ParamType, scope: Scope) -> type:
    """Return a concrete ctypes type, invoking `ctype` if it's a factory.

    Static types (classes like `ct.c_int` or an `ndpointer` subclass produced by
    `numpy.ctypeslib.ndpointer`) are returned unchanged. Callables that are not
    types are invoked with `scope` and expected to return a ctypes type.
    """
    if isinstance(ctype, type):
        return ctype
    return ctype(scope)


def ndptr_f64(*dim_keys: str) -> Callable[[Scope], type]:
    """Build a factory that resolves a contiguous `float64` ndpointer.

    The returned factory reads each `dim_keys` entry from the call scope
    (kwargs, always `ct.c_int` since dims are `POINTER(c_int)` params) and
    returns an `np.ctypeslib.ndpointer` subclass with the resolved shape.
    """

    def factory(scope: Scope) -> type:
        shape = tuple(scope[k].value for k in dim_keys)
        return np.ctypeslib.ndpointer(  # type: ignore[return-value]
            np.float64, shape=shape, flags=STR_C_CONTIGUOUS
        )

    return factory


def out_int(name: str) -> Param:
    """A C-int scalar output, allocated by `Routine.call` and returned."""
    return Param(name=name, ctype=ct.POINTER(ct.c_int), out=True)


def rc_policy(exc: type[Exception], msg: str) -> Callable[[int], None]:
    """Build a policy for routines that report `0` = OK, `1` = `exc(msg)`.

    Any other code raises `RuntimeError`.
    """

    def policy(rc: int) -> None:
        if rc == 1:
            raise exc(msg)
        if rc != 0:
            unexpected = f"unrecognized return code: {rc}"
            raise RuntimeError(unexpected)

    return policy


def attr_accessor_policy(rc: int) -> None:
    """Raise if `rc` is not `FvsAttrReturnCode.OK`.

    Consumed by the `rc_policy` field on `Routine` entries whose return codes
    follow the canonical attr-accessor convention shared by `fvsSpeciesAttr`,
    `fvsTreeAttr`, and similar routines. `FvsAttrReturnCode.NAME_NOT_FOUND`
    surfaces as `NameError` (a caller-supplied attribute name that FVS does not
    recognize); the remaining documented codes surface as `RuntimeError` with
    the enum's canned message. Codes outside the known set also become a
    `RuntimeError`, surfaced via the generic "unrecognized" message.
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
    # Keyed by un-mangled FVS routine name; params in Fortran declaration order.
    "fvs": Routine(
        params=(Param(name="itrncd", ctype=ct.POINTER(ct.c_int)),),
        rc_param=None,
    ),
    "fvsGetICCode": Routine(
        params=(out_int("ic_code"),),
        rc_param=None,
    ),
    "fvsGetRtnCode": Routine(
        params=(out_int("rtn_code"),),
        rc_param=None,
    ),
    "fvsGetRestartCode": Routine(
        params=(out_int("restart_code"),),
        rc_param=None,
    ),
    "fvsDimSizes": Routine(
        params=(
            out_int(STR_NTREES),
            out_int(STR_NCYCLES),
            out_int(STR_NPLOTS),
            out_int(STR_MAXTREES),
            out_int(STR_MAXSPECIES),
            out_int(STR_MAXPLOTS),
            out_int(STR_MAXCYCLES),
        ),
        rc_param=None,
    ),
    "fvsSetCmdLine": Routine(
        params=(
            Param(name="cmdline", ctype=ct.c_char_p),
            Param(name="nch", ctype=ct.POINTER(ct.c_int)),
            Param(name="itrncd", ctype=ct.POINTER(ct.c_int)),
        ),
        rc_param=None,
    ),
    "fvsSetStoppointCodes": Routine(
        params=(
            Param(name="stop_point_code", ctype=ct.POINTER(ct.c_int)),
            Param(name="stop_point_year", ctype=ct.POINTER(ct.c_int)),
        ),
        rc_param=None,
    ),
    "fvsStandID": Routine(
        params=(
            Param(name="stand_id", ctype=ct.c_char_p),
            Param(name="stand_cn", ctype=ct.c_char_p),
            Param(name="mgmt_id", ctype=ct.c_char_p),
            Param(name="stand_id_len", ctype=ct.POINTER(ct.c_int)),
            Param(name="stand_cn_len", ctype=ct.POINTER(ct.c_int)),
            Param(name="mgmt_id_len", ctype=ct.POINTER(ct.c_int)),
        ),
        rc_param=None,
    ),
    "fvsSpeciesCode": Routine(
        params=(
            Param(name="fvs_spp", ctype=ct.c_char_p),
            Param(name="fia_spp", ctype=ct.c_char_p),
            Param(name="plants_spp", ctype=ct.c_char_p),
            Param(name="index", ctype=ct.POINTER(ct.c_int)),
            Param(name="fvs_spp_len", ctype=ct.POINTER(ct.c_int)),
            Param(name="fia_spp_len", ctype=ct.POINTER(ct.c_int)),
            Param(name="plants_spp_len", ctype=ct.POINTER(ct.c_int)),
            out_int("rtncode"),
        ),
        rc_policy=rc_policy(IndexError, "Species index out of range"),
    ),
    "fvsSpeciesAttr": Routine(
        params=(
            Param(name="attr_name", ctype=ct.c_char_p),
            Param(name="nch", ctype=ct.POINTER(ct.c_int)),
            Param(name="action", ctype=ct.c_char_p),
            Param(
                name="arr",
                ctype=np.ctypeslib.ndpointer(
                    np.float64, flags=STR_C_CONTIGUOUS
                ),
            ),
            out_int("rtncode"),
        ),
        rc_policy=attr_accessor_policy,
    ),
    "fvsTreeAttr": Routine(
        params=(
            Param(name="attr_name", ctype=ct.c_char_p),
            Param(name="nch", ctype=ct.POINTER(ct.c_int)),
            Param(name="action", ctype=ct.c_char_p),
            Param(name=STR_NTREES, ctype=ct.POINTER(ct.c_int)),
            Param(name="arr", ctype=ndptr_f64(STR_NTREES)),
            out_int("rtncode"),
        ),
        rc_policy=attr_accessor_policy,
    ),
    "fvsFFEAttrs": Routine(
        params=(
            Param(name="attr_name", ctype=ct.c_char_p),
            Param(name="nch", ctype=ct.POINTER(ct.c_int)),
            Param(name="action", ctype=ct.c_char_p),
            Param(name=STR_MAXSPECIES, ctype=ct.POINTER(ct.c_int)),
            Param(name="arr", ctype=ndptr_f64(STR_MAXSPECIES)),
            out_int("rtncode"),
        ),
        rc_policy=attr_accessor_policy,
    ),
    "fvsSVSDimSizes": Routine(
        params=(
            out_int(STR_NSVSOBJS),
            out_int(STR_NDEADOBJS),
            out_int(STR_NCWDOBJS),
            out_int(STR_MXSVSOBJS),
            out_int(STR_MXDEADOBJS),
            out_int(STR_MXCWDOBJS),
        ),
        rc_param=None,
    ),
    "fvsSVSObjData": Routine(
        params=(
            Param(name="attr_name", ctype=ct.c_char_p),
            Param(name="nch", ctype=ct.POINTER(ct.c_int)),
            Param(name="action", ctype=ct.c_char_p),
            Param(name=STR_NOBJS, ctype=ct.POINTER(ct.c_int)),
            Param(name="arr", ctype=ndptr_f64(STR_NOBJS)),
            out_int("rtncode"),
        ),
        rc_policy=attr_accessor_policy,
    ),
    "fvsAddTrees": Routine(
        params=(
            Param(name="dbh", ctype=ndptr_f64(STR_NTREES)),
            Param(name="species", ctype=ndptr_f64(STR_NTREES)),
            Param(name="ht", ctype=ndptr_f64(STR_NTREES)),
            Param(name="cratio", ctype=ndptr_f64(STR_NTREES)),
            Param(name="plot", ctype=ndptr_f64(STR_NTREES)),
            Param(name="tpa", ctype=ndptr_f64(STR_NTREES)),
            Param(name=STR_NTREES, ctype=ct.POINTER(ct.c_int)),
            out_int("rtncode"),
        ),
        rc_policy=rc_policy(
            ValueError, "Not enough room to store the new trees"
        ),
    ),
    "fvsEvmonAttr": Routine(
        params=(
            Param(name="attr_name", ctype=ct.c_char_p),
            Param(name="nch", ctype=ct.POINTER(ct.c_int)),
            Param(name="action", ctype=ct.c_char_p),
            Param(
                name="arr", ctype=np.ctypeslib.ndpointer(np.float64, shape=(1,))
            ),
            out_int("rtncode"),
        ),
        rc_policy=attr_accessor_policy,
    ),
    "fvsAddActivity": Routine(
        params=(
            Param(name="year", ctype=ct.POINTER(ct.c_int)),
            Param(name="activity_code", ctype=ct.POINTER(ct.c_int)),
            Param(name="params", ctype=ndptr_f64("nparams")),
            Param(name="nparams", ctype=ct.POINTER(ct.c_int)),
            out_int("rtncode"),
        ),
        # The FVS API docs don't cover this return code; 1 = error per rFVS.
        rc_policy=rc_policy(
            ValueError, "fvsAddActivity failed to add the activity"
        ),
    ),
    "fvsSummary": Routine(
        params=(
            Param(
                name="summary",
                ctype=np.ctypeslib.ndpointer(np.intc, flags=STR_C_CONTIGUOUS),
            ),
            Param(name="icycle", ctype=ct.POINTER(ct.c_int)),
            Param(name="ncycles", ctype=ct.POINTER(ct.c_int)),
            Param(name="maxrow", ctype=ct.POINTER(ct.c_int)),
            Param(name="maxcol", ctype=ct.POINTER(ct.c_int)),
            out_int("rtncode"),
        ),
    ),
}


FVS_ROUTINES: Mapping[str, Routine] = MappingProxyType({
    k: replace(v, name=k) for k, v in _RAW_ROUTINES.items()
})
"""Immutable registry of FVS routine call descriptions.

Keyed by the un-mangled FVS routine name. `FvsCore` binds every entry at load
time, so a library missing any of them fails to load.
"""

"""Unit tests for :mod:`fvs2py._routines`.

The invoker dispatches ctypes calls without a loaded FVS library by relying
on plain Python callables as stand-ins for resolved foreign functions. These
tests exercise dispatch order, dynamic ctype resolution, OUT-param auto
allocation, return-code policy dispatch, and kwarg validation. Registry
invariants are asserted against the module-level :data:`FVS_ROUTINES`
mapping and stay vacuously true until later PRs populate it.
"""

from __future__ import annotations

import ctypes as ct

import numpy as np
import pytest

from fvs2py._routines import (
    FVS_ROUTINES,
    Intent,
    Param,
    Routine,
    _unwrap,
    attr_accessor_policy,
    ndptr_f64,
    ndptr_intc,
)
from fvs2py.enums import FvsAttrReturnCode


class _Stub:
    """Python callable usable as a ctypes ``_FuncPointer`` stand-in.

    Records positional args from the most recent call, permits ``argtypes``
    and ``restype`` attribute assignment (mirroring the ctypes API), and
    optionally runs a writer to populate OUT buffers.
    """

    def __init__(self, writer=None):
        self.calls: list[tuple] = []
        self.argtypes = None
        self.restype = None
        self._writer = writer

    def __call__(self, *args):
        self.calls.append(args)
        if self._writer is not None:
            self._writer(*args)


# ---------------------------------------------------------------------------
# Helpers: _unwrap, ndptr_* factories, attr_accessor_policy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [(7, 7), (ct.c_int(42), 42), (np.int32(5), 5)],
)
def test_unwrap_returns_int_for_plain_and_ctypes_and_numpy_scalars(
    value, expected
):
    assert _unwrap(value) == expected


def test_ndptr_f64_resolves_shape_and_dtype_from_scope():
    factory = ndptr_f64("rows", "cols")
    cls = factory({"rows": ct.c_int(2), "cols": 3})
    assert cls._shape_ == (2, 3)
    assert cls._dtype_ == np.dtype(np.float64)


def test_ndptr_intc_uses_intc_dtype():
    cls = ndptr_intc("n")({"n": 4})
    assert cls._shape_ == (4,)
    assert cls._dtype_ == np.dtype(np.intc)


@pytest.mark.parametrize(
    ("rc", "exc", "match"),
    [
        (int(FvsAttrReturnCode.OK), None, None),
        (int(FvsAttrReturnCode.NAME_NOT_FOUND), NameError, "name not found"),
        (
            int(FvsAttrReturnCode.NAME_LENGTH_INVALID),
            RuntimeError,
            "length of name string",
        ),
        (999, RuntimeError, "unrecognized attribute-accessor return code"),
    ],
)
def test_attr_accessor_policy_dispatches_by_return_code(rc, exc, match):
    if exc is None:
        assert attr_accessor_policy(rc) is None
    else:
        with pytest.raises(exc, match=match):
            attr_accessor_policy(rc)


# ---------------------------------------------------------------------------
# Routine.call — dispatch order and ctypes-binding side effects
# ---------------------------------------------------------------------------


def test_call_dispatches_positional_args_in_declaration_order():
    routine = Routine(
        params=(
            Param(name="a", ctype=ct.c_int),
            Param(name="b", ctype=ct.c_int),
            Param(name="c", ctype=ct.c_int),
        ),
        rc_param=None,
    )
    stub = _Stub()
    result = routine.call(stub, a=1, b=2, c=3)
    assert result is None
    assert stub.calls == [(1, 2, 3)]


def test_call_sets_argtypes_and_restype_on_func():
    routine = Routine(
        params=(Param(name="x", ctype=ct.c_int),),
        restype=ct.c_double,
        rc_param=None,
    )
    stub = _Stub()
    routine.call(stub, x=1)
    assert stub.argtypes == [ct.c_int]
    assert stub.restype is ct.c_double


def test_call_resolves_dynamic_ctype_factory_against_kwargs():
    routine = Routine(
        params=(
            Param(name="n", ctype=ct.POINTER(ct.c_int)),
            Param(name="arr", ctype=ndptr_f64("n"), intent=Intent.INOUT),
        ),
        rc_param=None,
    )
    stub = _Stub()
    arr = np.zeros(4, dtype=np.float64)
    routine.call(stub, n=ct.c_int(4), arr=arr)
    ndptr_cls = stub.argtypes[1]
    assert ndptr_cls._shape_ == (4,)
    assert ndptr_cls._dtype_ == np.dtype(np.float64)


# ---------------------------------------------------------------------------
# Routine.call — OUT auto-allocation and INOUT pass-through
# ---------------------------------------------------------------------------


def test_call_single_out_returns_unwrapped_scalar():
    routine = Routine(
        params=(
            Param(name="out", ctype=ct.POINTER(ct.c_int), intent=Intent.OUT),
        ),
        rc_param=None,
    )

    def writer(out):
        out.value = 42

    stub = _Stub(writer=writer)
    assert routine.call(stub) == 42


def test_call_multiple_outs_returned_as_dict_by_name():
    routine = Routine(
        params=(
            Param(name="a", ctype=ct.POINTER(ct.c_int), intent=Intent.OUT),
            Param(name="b", ctype=ct.POINTER(ct.c_int), intent=Intent.OUT),
            Param(name="c", ctype=ct.POINTER(ct.c_int), intent=Intent.OUT),
        ),
        rc_param=None,
    )

    def writer(a, b, c):
        a.value, b.value, c.value = 1, 2, 3

    stub = _Stub(writer=writer)
    assert routine.call(stub) == {"a": 1, "b": 2, "c": 3}


def test_call_inout_buffer_is_passed_by_reference_and_reflects_writes():
    routine = Routine(
        params=(
            Param(name="n", ctype=ct.POINTER(ct.c_int)),
            Param(name="buf", ctype=ndptr_f64("n"), intent=Intent.INOUT),
        ),
        rc_param=None,
    )

    def writer(n, buf):
        buf[:] = np.arange(n.value, dtype=np.float64)

    stub = _Stub(writer=writer)
    buf = np.zeros(3, dtype=np.float64)
    routine.call(stub, n=ct.c_int(3), buf=buf)
    assert stub.calls[0][1] is buf
    assert buf.tolist() == [0.0, 1.0, 2.0]


# ---------------------------------------------------------------------------
# Routine.call — rc_policy dispatch
# ---------------------------------------------------------------------------


def test_call_rc_policy_fires_with_return_code_value():
    called_with: list[int] = []

    def policy(rc):
        called_with.append(rc)
        if rc != 0:
            msg = f"boom rc={rc}"
            raise RuntimeError(msg)

    routine = Routine(
        params=(
            Param(
                name="rtncode",
                ctype=ct.POINTER(ct.c_int),
                intent=Intent.OUT,
            ),
        ),
        rc_policy=policy,
    )

    stub = _Stub(writer=lambda rtncode: setattr(rtncode, "value", 7))
    with pytest.raises(RuntimeError, match="boom rc=7"):
        routine.call(stub)
    assert called_with == [7]


def test_call_returns_non_rc_outs_excluding_rtncode():
    routine = Routine(
        params=(
            Param(
                name="value",
                ctype=ct.POINTER(ct.c_double),
                intent=Intent.OUT,
            ),
            Param(
                name="rtncode",
                ctype=ct.POINTER(ct.c_int),
                intent=Intent.OUT,
            ),
        ),
        rc_policy=lambda _rc: None,
    )

    def writer(value, rtncode):
        value.value = 3.5
        rtncode.value = 0

    stub = _Stub(writer=writer)
    assert routine.call(stub) == pytest.approx(3.5)


# ---------------------------------------------------------------------------
# Routine.call — kwarg validation
# ---------------------------------------------------------------------------


def test_call_missing_required_kwarg_raises_typeerror_with_name():
    routine = Routine(
        params=(
            Param(name="x", ctype=ct.c_int),
            Param(name="y", ctype=ct.c_int),
        ),
        rc_param=None,
        name="fvsStub",
    )
    with pytest.raises(TypeError, match=r"fvsStub.*missing.*\['y'\]"):
        routine.call(_Stub(), x=1)


def test_call_unknown_kwarg_raises_typeerror_with_name():
    routine = Routine(
        params=(Param(name="x", ctype=ct.c_int),),
        rc_param=None,
        name="fvsStub",
    )
    with pytest.raises(TypeError, match=r"fvsStub.*unknown.*\['extra'\]"):
        routine.call(_Stub(), x=1, extra=2)


def test_call_out_param_in_kwargs_raises_typeerror():
    routine = Routine(
        params=(
            Param(
                name="rtncode",
                ctype=ct.POINTER(ct.c_int),
                intent=Intent.OUT,
            ),
        ),
        name="fvsStub",
    )
    with pytest.raises(
        TypeError, match=r"fvsStub.*OUT params must not be provided"
    ):
        routine.call(_Stub(), rtncode=ct.c_int(0))


# ---------------------------------------------------------------------------
# FVS_ROUTINES registry invariants
#
# Each iterates over ``FVS_ROUTINES.items()`` and thus applies to every
# entry contributed by a mixin migration.
# ---------------------------------------------------------------------------


def test_registry_entries_carry_their_mapping_key_as_name():
    for key, routine in FVS_ROUTINES.items():
        assert routine.name == key


# ---------------------------------------------------------------------------
# Routine.__post_init__ — structural validation at construction time
# ---------------------------------------------------------------------------


def test_post_init_rejects_rc_policy_without_rc_param():
    with pytest.raises(ValueError, match="rc_policy requires rc_param"):
        Routine(
            params=(
                Param(
                    name="out",
                    ctype=ct.POINTER(ct.c_int),
                    intent=Intent.OUT,
                ),
            ),
            rc_param=None,
            rc_policy=lambda _rc: None,
            name="fvsStub",
        )


def test_post_init_rejects_rc_param_not_naming_an_out_param():
    with pytest.raises(
        ValueError, match="rc_param 'missing' must name an Intent.OUT param"
    ):
        Routine(
            params=(
                Param(
                    name="rtncode",
                    ctype=ct.POINTER(ct.c_int),
                    intent=Intent.OUT,
                ),
            ),
            rc_param="missing",
            rc_policy=lambda _rc: None,
            name="fvsStub",
        )


def test_post_init_rejects_rc_param_naming_non_out_intent():
    with pytest.raises(
        ValueError, match="rc_param 'x' must name an Intent.OUT param"
    ):
        Routine(
            params=(Param(name="x", ctype=ct.POINTER(ct.c_int)),),
            rc_param="x",
            rc_policy=lambda _rc: None,
            name="fvsStub",
        )


def test_post_init_allows_rc_param_without_rc_policy():
    # Routine reports a return code but we don't care about it; no policy is
    # a legitimate opt-out and must not be rejected.
    Routine(
        params=(Param(name="x", ctype=ct.c_int),),
        rc_param="rtncode",
        rc_policy=None,
    )


# ---------------------------------------------------------------------------
# End-to-end: attr-accessor shape exercised via an inline Routine
#
# Composes every piece (Intent, dynamic ``ndptr_f64`` factory,
# ``attr_accessor_policy``, OUT auto-allocation, kwarg dispatch) without
# depending on a registry entry. Once :data:`FVS_ROUTINES` carries
# ``fvsTreeAttr`` (or similar), this pattern is exactly what the mixin call
# site will hand to :meth:`FvsCore._invoke`.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("rc", "expected_exc", "expected_match"),
    [
        (int(FvsAttrReturnCode.OK), None, None),
        (int(FvsAttrReturnCode.NAME_NOT_FOUND), NameError, "name not found"),
    ],
)
def test_attr_accessor_shape_end_to_end(rc, expected_exc, expected_match):
    routine = Routine(
        params=(
            Param(name="attr", ctype=ct.c_char_p),
            Param(name="nattr", ctype=ct.POINTER(ct.c_int)),
            Param(name="action", ctype=ct.c_char_p),
            Param(name="ntrees", ctype=ct.POINTER(ct.c_int)),
            Param(
                name="values",
                ctype=ndptr_f64("ntrees"),
                intent=Intent.INOUT,
            ),
            Param(
                name="rtncode",
                ctype=ct.POINTER(ct.c_int),
                intent=Intent.OUT,
            ),
        ),
        rc_policy=attr_accessor_policy,
        name="fvsTreeAttrLike",
    )

    def writer(_attr, _nattr, _action, ntrees, values, rtncode):
        rtncode.value = rc
        if rc == 0:
            values[:] = np.arange(ntrees.value, dtype=np.float64) * 10

    stub = _Stub(writer=writer)
    values = np.zeros(3, dtype=np.float64)
    kwargs = {
        "attr": b"dbh",
        "nattr": ct.c_int(3),
        "action": b"get",
        "ntrees": ct.c_int(3),
        "values": values,
    }

    if expected_exc is None:
        assert routine.call(stub, **kwargs) is None
        assert values.tolist() == [0.0, 10.0, 20.0]
    else:
        with pytest.raises(expected_exc, match=expected_match):
            routine.call(stub, **kwargs)

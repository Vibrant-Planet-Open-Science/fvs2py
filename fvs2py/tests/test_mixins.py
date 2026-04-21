"""Stub-based unit tests for the focused mixins under ``fvs2py._mixins``.

These tests exercise each mixin's Python-side logic without loading the real
FVS shared library. Where a mixin method has to invoke a ctypes foreign
function, the test substitutes a plain Python callable that mutates its
output-pointer arguments (the ``call_out`` helper passes freshly-allocated
``ct.c_int`` objects, which look identical to a Python stub).
"""

from __future__ import annotations

import ctypes as ct

import pytest

from fvs2py._mixins.control import ControlMixin
from fvs2py._mixins.simulation import SimulationMixin
from fvs2py._mixins.species import SpeciesMixin
from fvs2py._mixins.stand import StandMixin
from fvs2py._routines import FVS_ROUTINES
from fvs2py.common import class_requires_fvs_library, no_fvs_library_required
from fvs2py.constants import (
    MGMT_ID_COLUMN_NAME,
    SPECIES_ATTRS,
    STAND_CN_COLUMN_NAME,
    STAND_ID_COLUMN_NAME,
    STR_MAXCYCLES,
    STR_MAXPLOTS,
    STR_MAXSPECIES,
    STR_MAXTREES,
    STR_NCYCLES,
    STR_NPLOTS,
    STR_NTREES,
)
from fvs2py.enums import (
    FvsAttributeAccessor,
    FvsItrnCode,
    FvsRestartCode,
    FvsSimulationState,
)


class _StubLib:
    """Sentinel `_lib` attribute used by `@fvs_property` loaded-library checks."""


# ---------------------------------------------------------------------------
# StandMixin
# ---------------------------------------------------------------------------


class _StandStub(StandMixin, ControlMixin):
    """Minimal StandMixin host that uses Python-callable stubs for ctypes calls.

    Also inherits ControlMixin so ``stop_point_code`` resolves as a property.
    """

    def __init__(self):
        self._lib = _StubLib()
        self.keyfile = None
        self._stop_point_code = None
        self._stop_point_year = None
        self._stand_id = ct.create_string_buffer(26)
        self._stand_cn = ct.create_string_buffer(40)
        self._mgmt_id = ct.create_string_buffer(4)

        def fvs_dim_sizes(
            ntrees, ncycles, nplots, maxtrees, maxspecies, maxplots, maxcycles
        ):
            ntrees.value = 11
            ncycles.value = 22
            nplots.value = 33
            maxtrees.value = 44
            maxspecies.value = 55
            maxplots.value = 66
            maxcycles.value = 77

        def fvs_stand_id(stand_id, stand_cn, mgmt_id, *_lengths):
            stand_id.value = b"stand-001"
            stand_cn.value = b"cn-42"
            mgmt_id.value = b"M1"

        self._fvsDimSizes = fvs_dim_sizes
        self._fvsStandID = fvs_stand_id

    def _invoke(self, name, /, **kwargs):
        return FVS_ROUTINES[name].call(getattr(self, f"_{name}"), **kwargs)


def test_stand_mixin_dims_returns_named_dict():
    stub = _StandStub()
    assert stub.dims == {
        STR_NTREES: 11,
        STR_NCYCLES: 22,
        STR_NPLOTS: 33,
        STR_MAXTREES: 44,
        STR_MAXSPECIES: 55,
        STR_MAXPLOTS: 66,
        STR_MAXCYCLES: 77,
    }


def test_stand_mixin_stand_ids_without_keyfile_raises():
    stub = _StandStub()
    with pytest.raises(AttributeError, match="Keyfile not loaded yet."):
        stub.stand_ids


def test_stand_mixin_stand_ids_without_run_raises():
    stub = _StandStub()
    stub.keyfile = "STDIDENT\n"
    with pytest.raises(
        RuntimeError,
        match="No inventory data loaded yet. Call `run` method.",
    ):
        stub.stand_ids


def test_stand_mixin_stand_ids_returns_decoded_values():
    stub = _StandStub()
    stub.keyfile = "STDIDENT\n"
    stub._stop_point_code = ct.c_int(0)
    assert stub.stand_ids == {
        STAND_ID_COLUMN_NAME: "stand-001",
        STAND_CN_COLUMN_NAME: "cn-42",
        MGMT_ID_COLUMN_NAME: "M1",
    }


# ---------------------------------------------------------------------------
# SimulationMixin
# ---------------------------------------------------------------------------


class _SimulationStub(SimulationMixin):
    """Minimal SimulationMixin host with writer-based ctypes stubs.

    The ``_fvs`` stub is a no-op so :meth:`SimulationMixin.run` can exercise
    its control flow without a real FVS library. :meth:`set_stop_point_codes`
    is stubbed to a no-op as well; tests that want to observe or override it
    assign directly on the instance. ``_invoke`` mirrors
    :meth:`fvs2py._core.FvsCore._invoke` so the mixin exercises the real
    registry against the attribute-level stubs bound below.
    """

    def __init__(self, itrncd=0, exit_code=0, restart_code=0):
        self._lib = _StubLib()
        self.keyfile = None
        self._itrncd = ct.c_int(-1)
        self._state = FvsSimulationState.IDLE
        # SimulationMixin.run() reads these via an f-string in logging.debug,
        # so they must exist regardless of log level.
        self.stop_point_code = 0
        self.stop_point_year = 0
        self.fvs_call_count = 0

        def writer(value):
            def _f(out):
                out.value = value

            return _f

        def fvs(_itrncd_ptr):
            self.fvs_call_count += 1

        self._fvsGetRtnCode = writer(itrncd)
        self._fvsGetICCode = writer(exit_code)
        self._fvsGetRestartCode = writer(restart_code)
        self._fvs = fvs
        self.set_stop_point_codes = lambda *_args: None

    def _invoke(self, name, /, **kwargs):
        return FVS_ROUTINES[name].call(getattr(self, f"_{name}"), **kwargs)


def test_simulation_mixin_itrncd_reads_fvs_output():
    stub = _SimulationStub(itrncd=2)
    assert stub.itrncd == 2


def test_simulation_mixin_exit_code_reads_fvs_output():
    stub = _SimulationStub(exit_code=3)
    assert stub.exit_code == 3


def test_simulation_mixin_restart_code_reads_fvs_output():
    stub = _SimulationStub(restart_code=100)
    assert stub.restart_code == 100


def test_simulation_mixin_run_without_keyfile_raises():
    stub = _SimulationStub()
    with pytest.raises(AttributeError, match="No keyfile loaded yet."):
        stub.run()


def test_simulation_mixin_run_guards_against_reentrant_call():
    stub = _SimulationStub(itrncd=int(FvsItrnCode.FINISHED_ALL_STANDS))
    stub.keyfile = "STDIDENT\n"
    stub._state = FvsSimulationState.RUNNING
    with pytest.raises(RuntimeError, match="Simulation already in progress"):
        stub.run()


def test_simulation_mixin_run_sets_state_complete_on_success():
    # itrncd != GOOD_RUNNING_STATE → loop never enters; restart_code != DONE →
    # no flush call. We only observe the state transition IDLE → COMPLETE.
    stub = _SimulationStub(itrncd=int(FvsItrnCode.FINISHED_ALL_STANDS))
    stub.keyfile = "STDIDENT\n"
    stub.run()
    assert stub._state == FvsSimulationState.COMPLETE
    assert stub.fvs_call_count == 0


def test_simulation_mixin_run_flushes_when_stand_done():
    # restart_code == DONE_RUNNING_STAND and itrncd already at FINISHED_ALL_STANDS
    # means the while-loop exits immediately but the flush call still fires.
    stub = _SimulationStub(
        itrncd=int(FvsItrnCode.FINISHED_ALL_STANDS),
        restart_code=int(FvsRestartCode.DONE_RUNNING_STAND),
    )
    stub.keyfile = "STDIDENT\n"
    stub.run()
    assert stub.fvs_call_count == 1
    assert stub._state == FvsSimulationState.COMPLETE


def test_simulation_mixin_run_sets_state_error_on_exception():
    # itrncd=GOOD_RUNNING_STATE forces the while-loop to call _fvs at least
    # once; we make that call blow up to exercise the state=ERROR transition.
    stub = _SimulationStub(itrncd=int(FvsItrnCode.GOOD_RUNNING_STATE))
    stub.keyfile = "STDIDENT\n"

    def boom(_itrncd_ptr):
        msg = "boom"
        raise RuntimeError(msg)

    stub._fvs = boom
    with pytest.raises(RuntimeError, match="boom"):
        stub.run()
    assert stub._state == FvsSimulationState.ERROR


def test_simulation_mixin_run_batch_without_keyfile_raises():
    stub = _SimulationStub()
    with pytest.raises(AttributeError, match="No keyfile loaded yet."):
        stub.run_batch()


def test_simulation_mixin_run_batch_guards_against_reentrant_call():
    stub = _SimulationStub(itrncd=int(FvsItrnCode.FINISHED_ALL_STANDS))
    stub.keyfile = "STDIDENT\n"
    stub._state = FvsSimulationState.RUNNING
    with pytest.raises(RuntimeError, match="Simulation already in progress"):
        stub.run_batch()


def test_simulation_mixin_run_batch_does_not_flush_on_stand_done():
    # Identical setup to test_simulation_mixin_run_flushes_when_stand_done
    # but via run_batch: itrncd starts at FINISHED_ALL_STANDS (loop skipped)
    # and restart_code == DONE_RUNNING_STAND. run() would emit one flush _fvs
    # call; run_batch must NOT.
    stub = _SimulationStub(
        itrncd=int(FvsItrnCode.FINISHED_ALL_STANDS),
        restart_code=int(FvsRestartCode.DONE_RUNNING_STAND),
    )
    stub.keyfile = "STDIDENT\n"
    stub.run_batch()
    assert stub.fvs_call_count == 0
    assert stub._state == FvsSimulationState.COMPLETE


def test_simulation_mixin_run_batch_sets_state_error_on_exception():
    stub = _SimulationStub(itrncd=int(FvsItrnCode.GOOD_RUNNING_STATE))
    stub.keyfile = "STDIDENT\n"

    def boom(_itrncd_ptr):
        msg = "boom"
        raise RuntimeError(msg)

    stub._fvs = boom
    with pytest.raises(RuntimeError, match="boom"):
        stub.run_batch()
    assert stub._state == FvsSimulationState.ERROR


# ---------------------------------------------------------------------------
# ControlMixin
# ---------------------------------------------------------------------------


class _ControlStub(ControlMixin):
    def __init__(self):
        self._lib = _StubLib()
        self._itrncd = ct.c_int(FvsItrnCode.NOT_STARTED)
        self._stop_point_code = None
        self._stop_point_year = None
        self._fvsSetStoppointCodes = lambda *_args: None

    def _invoke(self, name, /, **kwargs):
        return FVS_ROUTINES[name].call(getattr(self, f"_{name}"), **kwargs)


def test_control_mixin_stop_point_code_returns_none_when_unset():
    stub = _ControlStub()
    assert stub.stop_point_code is None


def test_control_mixin_stop_point_year_returns_none_when_unset():
    stub = _ControlStub()
    assert stub.stop_point_year is None


def test_control_mixin_set_stop_point_codes_populates_buffers():
    stub = _ControlStub()
    stub.set_stop_point_codes(3, 2025)
    assert stub.stop_point_code == 3
    assert stub.stop_point_year == 2025


@pytest.mark.parametrize("invalid", [-2, 8, 10, -5])
def test_control_mixin_set_stop_point_codes_rejects_out_of_range(invalid):
    stub = _ControlStub()
    with pytest.raises(ValueError, match="Invalid value for stop_point_code"):
        stub.set_stop_point_codes(invalid, 0)


def test_control_mixin_set_stop_point_codes_rejects_year_without_code():
    stub = _ControlStub()
    with pytest.raises(
        ValueError,
        match="Must specify stop_point_year if also specifying stop_point_code",
    ):
        stub.set_stop_point_codes(None, 2025)


def test_control_mixin_stop_point_code_setter_delegates():
    stub = _ControlStub()
    stub.stop_point_code = 3
    assert stub.stop_point_code == 3
    assert stub.stop_point_year == 0


def test_control_mixin_stop_point_year_setter_delegates():
    stub = _ControlStub()
    stub.stop_point_year = 2025
    assert stub.stop_point_code == 0
    assert stub.stop_point_year == 2025


def test_control_mixin_stop_point_code_setter_preserves_existing_year():
    stub = _ControlStub()
    stub.set_stop_point_codes(1, 2020)
    stub.stop_point_code = 4
    assert stub.stop_point_code == 4
    assert stub.stop_point_year == 2020


def test_control_mixin_stop_point_year_setter_preserves_existing_code():
    stub = _ControlStub()
    stub.set_stop_point_codes(2, 2015)
    stub.stop_point_year = 2030
    assert stub.stop_point_code == 2
    assert stub.stop_point_year == 2030


def test_control_mixin_stop_point_code_setter_validates():
    stub = _ControlStub()
    with pytest.raises(ValueError, match="Invalid value for stop_point_code"):
        stub.stop_point_code = 99


# ---------------------------------------------------------------------------
# SpeciesMixin
# ---------------------------------------------------------------------------


class _SpeciesStub(SpeciesMixin):
    def __init__(self):
        self._lib = _StubLib()
        self._species_attrs = dict.fromkeys(SPECIES_ATTRS)


def test_species_mixin_species_attr_unknown_name_raises_nameerror():
    stub = _SpeciesStub()
    with pytest.raises(NameError, match="Invalid variable requested"):
        stub._species_attr("not-a-real-attr", FvsAttributeAccessor.GET)


def test_species_mixin_species_attr_set_without_arr_raises_typeerror():
    stub = _SpeciesStub()
    # `_species_attr` reads `self.dims` before the arr-None guard; since
    # `dims` is not on SpeciesMixin, an instance attribute shadows fine.
    stub.dims = {STR_MAXSPECIES: 1}
    attr = next(iter(SPECIES_ATTRS))
    with pytest.raises(
        TypeError, match="Must provide `arr` if `action` is 'set'"
    ):
        stub._species_attr(attr, FvsAttributeAccessor.SET, None)


# ---------------------------------------------------------------------------
# class_requires_fvs_library: MRO walk, marker opt-out, static/class skip
# ---------------------------------------------------------------------------


def test_class_requires_fvs_library_wraps_public_methods_from_mixins():
    class MixinA:
        def alpha(self):
            return "alpha"

    class MixinB:
        def beta(self):
            return "beta"

    @class_requires_fvs_library
    class Host(MixinA, MixinB):
        pass

    obj = Host()
    obj._lib = None
    with pytest.raises(
        RuntimeError, match="FVS library not loaded, unable to call alpha."
    ):
        obj.alpha()
    with pytest.raises(
        RuntimeError, match="FVS library not loaded, unable to call beta."
    ):
        obj.beta()


def test_class_requires_fvs_library_subclass_override_wins_over_base():
    class Base:
        def method(self):
            return "base"

    @class_requires_fvs_library
    class Sub(Base):
        def method(self):
            return "sub"

    obj = Sub()
    obj._lib = _StubLib()
    assert obj.method() == "sub"


def test_class_requires_fvs_library_honors_no_fvs_library_required():
    @class_requires_fvs_library
    class Host:
        @no_fvs_library_required
        def pure_python(self):
            return "ok"

        def needs_lib(self):
            return "guarded"

    obj = Host()
    obj._lib = None
    assert obj.pure_python() == "ok"
    with pytest.raises(
        RuntimeError, match="FVS library not loaded, unable to call needs_lib."
    ):
        obj.needs_lib()


def test_class_requires_fvs_library_skips_staticmethod_and_classmethod():
    @class_requires_fvs_library
    class Host:
        @staticmethod
        def static_method():
            return "static"

        @classmethod
        def class_method(cls):
            return "class"

    # `_lib` is not set on any instance — a wrapped method would raise
    # RuntimeError. These are NOT wrapped, so they work without state.
    assert Host.static_method() == "static"
    assert Host.class_method() == "class"


def test_class_requires_fvs_library_skips_private_methods():
    @class_requires_fvs_library
    class Host:
        def _private(self):
            return "private"

    obj = Host()
    obj._lib = None
    assert obj._private() == "private"


def test_class_requires_fvs_library_skips_property_descriptors():
    @class_requires_fvs_library
    class Host:
        @property
        def plain(self):
            return "plain"

    obj = Host()
    obj._lib = None
    assert obj.plain == "plain"

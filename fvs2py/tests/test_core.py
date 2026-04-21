import ctypes as ct

import pytest

from fvs2py._core import FvsCore
from fvs2py.constants import NEEDED_ROUTINES


@pytest.mark.usefixtures("mock_valid_fvs_dll")
def test_valid_cdll_load():
    fvs = FvsCore("/not/a/real/dir/FVSxx.so")

    assert fvs.variant == "XX"
    for routine in NEEDED_ROUTINES:
        assert hasattr(fvs, f"_{routine}")


@pytest.mark.usefixtures("mock_invalid_fvs_dll")
def test_missing_routines():
    msg = " ".join(
        [
            ", ".join([*NEEDED_ROUTINES[1:]]),
            "are needed routines that are not available in library, "
            "(maybe they weren't exported when library was built)",
        ]
    )
    with pytest.raises(ImportError) as excinfo:
        FvsCore("/not/a/real/dir/FVSxx.so")

    assert excinfo.type is ImportError
    assert str(excinfo.value) == msg


@pytest.mark.usefixtures("mock_another_invalid_fvs_dll")
def test_routine_not_callable():
    msg = " ".join(
        [
            ", ".join(NEEDED_ROUTINES),
            "are needed routines that are not available in library, "
            "(maybe they weren't exported when library was built)",
        ]
    )
    with pytest.raises(ImportError) as excinfo:
        FvsCore("/not/a/real/dir/FVSxx.so")

    assert excinfo.type is ImportError
    assert str(excinfo.value) == msg


@pytest.mark.usefixtures("mock_valid_reformatted_fvs_dll")
def test_cdll_load_reformatted_routines():
    fvs = FvsCore("/not/a/real/dir/FVSyz.so")

    assert fvs.variant == "YZ"
    for routine in NEEDED_ROUTINES:
        assert hasattr(fvs, f"_{routine}")


# ---------------------------------------------------------------------------
# FvsCore._invoke — dispatch through FVS_ROUTINES
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_valid_fvs_dll")
def test_invoke_dispatches_to_registered_routine_and_returns_out_value():
    fvs = FvsCore("/not/a/real/dir/FVSxx.so")

    def writer(code):
        code.value = 7

    fvs._fvsGetICCode = writer
    assert fvs._invoke("fvsGetICCode") == 7


@pytest.mark.usefixtures("mock_valid_fvs_dll")
def test_invoke_passes_inout_buffer_through_to_foreign_function():
    fvs = FvsCore("/not/a/real/dir/FVSxx.so")
    captured: list[ct.c_int] = []

    def fvs_stub(itrncd):
        captured.append(itrncd)
        itrncd.value = 2

    fvs._fvs = fvs_stub
    itrncd = ct.c_int(0)
    assert fvs._invoke("fvs", itrncd=itrncd) is None
    assert captured == [itrncd]
    assert itrncd.value == 2


@pytest.mark.usefixtures("mock_valid_fvs_dll")
def test_invoke_unknown_routine_raises_notimplementederror_with_name():
    fvs = FvsCore("/not/a/real/dir/FVSxx.so")
    with pytest.raises(
        NotImplementedError,
        match="'fvsNotARoutine' is not registered in FVS_ROUTINES",
    ):
        fvs._invoke("fvsNotARoutine")

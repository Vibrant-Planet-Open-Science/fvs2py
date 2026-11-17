import pytest

from fvs2py._core import FvsCore
from fvs2py._routines import FVS_ROUTINES


@pytest.mark.usefixtures("mock_valid_fvs_dll")
def test_valid_cdll_load():
    fvs = FvsCore("/not/a/real/dir/FVSxx.so")

    assert fvs.variant == "XX"


@pytest.mark.usefixtures("mock_invalid_fvs_dll")
def test_missing_routines_are_named_in_importerror():
    with pytest.raises(ImportError) as excinfo:
        FvsCore("/not/a/real/dir/FVSxx.so")
    missing = set(FVS_ROUTINES) - {"fvs"}
    assert all(name in str(excinfo.value) for name in missing)


@pytest.mark.usefixtures("mock_another_invalid_fvs_dll")
def test_non_callable_routine_counts_as_missing():
    with pytest.raises(ImportError, match=r"\bfvs\b"):
        FvsCore("/not/a/real/dir/FVSxx.so")


@pytest.mark.usefixtures("mock_valid_reformatted_fvs_dll")
def test_cdll_load_reformatted_routines():
    fvs = FvsCore("/not/a/real/dir/FVSyz.so")

    assert fvs.variant == "YZ"

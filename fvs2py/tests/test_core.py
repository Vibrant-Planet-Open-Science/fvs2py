import sys
import types
from pathlib import Path

import pytest

from fvs2py._core import FvsCore
from fvs2py._routines import FVS_ROUTINES


@pytest.mark.usefixtures("mock_valid_fvs_dll")
def test_valid_cdll_load():
    fvs = FvsCore(lib_path="/not/a/real/dir/FVSxx.so")

    assert fvs.variant == "XX"


@pytest.mark.usefixtures("mock_invalid_fvs_dll")
def test_missing_routines_are_named_in_importerror():
    with pytest.raises(ImportError) as excinfo:
        FvsCore(lib_path="/not/a/real/dir/FVSxx.so")
    missing = set(FVS_ROUTINES) - {"fvs"}
    assert all(name in str(excinfo.value) for name in missing)


@pytest.mark.usefixtures("mock_another_invalid_fvs_dll")
def test_non_callable_routine_counts_as_missing():
    with pytest.raises(ImportError, match=r"\bfvs\b"):
        FvsCore(lib_path="/not/a/real/dir/FVSxx.so")


@pytest.mark.usefixtures("mock_valid_reformatted_fvs_dll")
def test_cdll_load_reformatted_routines():
    fvs = FvsCore(lib_path="/not/a/real/dir/FVSyz.so")

    assert fvs.variant == "YZ"


@pytest.fixture
def fake_fvs_runtime(monkeypatch):
    module = types.SimpleNamespace(
        library_path=lambda v: Path(f"/fvs_runtime/lib/FVS{v.lower()}.so")
    )
    monkeypatch.setitem(sys.modules, "fvs_runtime", module)


@pytest.mark.usefixtures("mock_valid_fvs_dll", "fake_fvs_runtime")
def test_variant_loads_fvs_runtime_library():
    fvs = FvsCore("PN")

    assert fvs.lib_path == Path("/fvs_runtime/lib/FVSpn.so").resolve()
    assert fvs.variant == "PN"


def test_variant_without_fvs_runtime_names_the_extra(monkeypatch):
    monkeypatch.setitem(sys.modules, "fvs_runtime", None)
    with pytest.raises(ImportError, match=r"fvs2py\[runtime\]"):
        FvsCore("pn")


@pytest.mark.parametrize(
    "kwargs", [{}, {"lib_path": "/x/FVSpn.so", "variant": "pn"}]
)
def test_needs_exactly_one_of_lib_path_and_variant(kwargs):
    with pytest.raises(TypeError):
        FvsCore(**kwargs)

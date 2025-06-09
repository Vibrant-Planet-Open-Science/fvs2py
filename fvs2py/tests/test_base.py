import importlib.resources
import os

import pytest

from fvs2py._base import FVS

TEST_DLL = "/usr/local/lib/FVSso.so"
TEST_KEYFILE_PATH = importlib.resources.files("fvs2py.tests.keyfiles").joinpath(
    "SO.key"
)
FVS_RESTART_CODE_DONE_RUNNING_STAND = 100
FVS_RESTART_CODE_INITIALIZED = 0
FVS_STOP_POINT_CODE_AFTER_FIRST_EVMON = 2

FVS_ITRNCD_NOT_STARTED = -1
FVS_ITRNCD_GOOD_RUNNING_STATE = 0
FVS_ITRNCD_FINISHED_ALL_STANDS = 2


@pytest.fixture
def fvs():
    return FVS(TEST_DLL)


def test_load_keyfile(fvs, tmp_path):
    """Checks that keyfile attributes get populated and itrncd updates."""
    assert fvs.itrncd == FVS_ITRNCD_NOT_STARTED
    assert fvs.keyfile is None
    assert fvs.keyfile_path is None
    keyfile_content = TEST_KEYFILE_PATH.read_text()
    keyfile_to_run = tmp_path / "test_keyfile.key"

    with open(keyfile_to_run, "w") as f:
        f.write(keyfile_content)

    fvs.load_keyfile(keyfile_to_run)
    assert fvs.itrncd == FVS_ITRNCD_GOOD_RUNNING_STATE
    assert fvs.keyfile_path == keyfile_to_run
    assert fvs.keyfile == TEST_KEYFILE_PATH.read_text()


def test_stop_points(fvs):
    """Checks that stop point code and year works."""
    assert fvs.stop_point_code is None
    assert fvs.stop_point_year is None

    fvs.set_stop_point_codes(-1, 0)
    assert fvs.stop_point_code == -1
    assert fvs.stop_point_year == 0


def test_stop_point_year_without_stop_point_code(fvs):
    assert fvs.stop_point_code is None
    assert fvs.stop_point_year is None
    match_msg = (
        "Must specify stop_point_year if also specifying stop_point_code"
    )
    with pytest.raises(ValueError, match=match_msg):
        fvs.set_stop_point_codes(None, 0)


@pytest.mark.parametrize("stop_point_code", range(-2, 10))
def test_invalid_stop_point_code(fvs, stop_point_code):
    assert fvs.stop_point_code is None
    assert fvs.stop_point_year is None
    match_msg = "Invalid value for stop_point_code"
    if stop_point_code not in range(-1, 8):
        with pytest.raises(ValueError, match=match_msg):
            fvs.set_stop_point_codes(stop_point_code, 0)
    else:
        fvs.set_stop_point_codes(stop_point_code, 0)
        assert fvs.stop_point_code == stop_point_code
        assert fvs.stop_point_year == 0


def test_run_with_keyfile_succeeds(fvs, tmp_path):
    assert fvs.itrncd == FVS_ITRNCD_NOT_STARTED
    keyfile_content = TEST_KEYFILE_PATH.read_text()
    keyfile_to_run = tmp_path / "test_keyfile.key"

    with open(keyfile_to_run, "w") as f:
        f.write(keyfile_content)

    fvs.load_keyfile(keyfile_to_run)
    assert fvs.restart_code == FVS_RESTART_CODE_INITIALIZED
    fvs.run()
    assert fvs.restart_code == FVS_RESTART_CODE_DONE_RUNNING_STAND
    assert fvs.itrncd == FVS_ITRNCD_GOOD_RUNNING_STATE
    fvs.run()
    assert fvs.itrncd == FVS_ITRNCD_FINISHED_ALL_STANDS
    assert os.path.exists(f"{tmp_path}/test_keyfile.out")


def test_run_without_keyfile_raises(fvs):
    with pytest.raises(AttributeError, match="No keyfile loaded yet."):
        fvs.run()


def test_restart_codes_match_stop_point_codes(fvs, tmp_path):
    assert fvs.itrncd == FVS_ITRNCD_NOT_STARTED
    assert fvs.stop_point_code is None
    assert fvs.stop_point_year is None
    assert fvs.restart_code == FVS_RESTART_CODE_INITIALIZED

    keyfile_content = TEST_KEYFILE_PATH.read_text()
    keyfile_to_run = tmp_path / "test_keyfile.key"

    with open(keyfile_to_run, "w") as f:
        f.write(keyfile_content)

    fvs.load_keyfile(keyfile_to_run)
    assert fvs.restart_code == FVS_RESTART_CODE_INITIALIZED
    fvs.run(
        stop_point_code=FVS_STOP_POINT_CODE_AFTER_FIRST_EVMON,
        stop_point_year=2010,
    )
    assert fvs.restart_code == FVS_STOP_POINT_CODE_AFTER_FIRST_EVMON
    assert fvs.itrncd == FVS_ITRNCD_GOOD_RUNNING_STATE
    fvs.run()
    assert fvs.restart_code == FVS_RESTART_CODE_DONE_RUNNING_STAND
    assert fvs.itrncd == FVS_ITRNCD_GOOD_RUNNING_STATE
    fvs.run()
    assert fvs.itrncd == FVS_ITRNCD_FINISHED_ALL_STANDS
    assert os.path.exists(f"{tmp_path}/test_keyfile.out")

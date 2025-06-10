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

FVS_EXIT_CODE_INPUT_DATA_ERROR = 1
FVS_EXIT_CODE_KEYWORD_ERROR = 2
FVS_EXIT_CODE_NO_ERROR = 0

FVSSO_START_DIMS = {
    "ntrees": 0,
    "ncycles": 0,
    "nplots": 0,
    "maxtrees": 3000,
    "maxspecies": 33,
    "maxplots": 500,
    "maxcycles": 40,
}
FVSOP_START_DIMS = {
    "ntrees": 0,
    "ncycles": 0,
    "nplots": 0,
    "maxtrees": 2000,
    "maxspecies": 39,
    "maxplots": 500,
    "maxcycles": 40,
}
SO_KEYFILE_STAND_IDS = {"stand_id": "12345", "stand_cn": "", "mgmt_id": "NONE"}


def test_load_keyfile(tmp_path):
    """Checks that keyfile attributes get populated and itrncd updates."""
    fvs = FVS(TEST_DLL)
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
    fvs._close()


def test_stop_points():
    """Checks that stop point code and year works."""
    fvs = FVS(TEST_DLL)
    assert fvs.stop_point_code is None
    assert fvs.stop_point_year is None

    fvs.set_stop_point_codes(-1, 0)
    assert fvs.stop_point_code == -1
    assert fvs.stop_point_year == 0
    fvs._close()


def test_stop_point_year_without_stop_point_code():
    fvs = FVS(TEST_DLL)
    assert fvs.stop_point_code is None
    assert fvs.stop_point_year is None
    match_msg = (
        "Must specify stop_point_year if also specifying stop_point_code"
    )
    with pytest.raises(ValueError, match=match_msg):
        fvs.set_stop_point_codes(None, 0)
    fvs._close()


@pytest.mark.parametrize("stop_point_code", range(-2, 10))
def test_invalid_stop_point_code(stop_point_code):
    fvs = FVS(TEST_DLL)
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
    fvs._close()


def test_run_with_keyfile_succeeds(tmp_path):
    fvs = FVS(TEST_DLL)
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
    fvs._close()


def test_run_without_keyfile_raises():
    fvs = FVS(TEST_DLL)
    with pytest.raises(AttributeError, match="No keyfile loaded yet."):
        fvs.run()
    fvs._close()


def test_restart_codes_match_stop_point_codes(tmp_path):
    fvs = FVS(TEST_DLL)
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
    fvs._close()


def test_exit_code_valid_run(tmp_path):
    fvs = FVS(TEST_DLL)
    assert fvs.exit_code == 0
    keyfile_content = TEST_KEYFILE_PATH.read_text()
    keyfile_to_run = tmp_path / "test_keyfile.key"

    with open(keyfile_to_run, "w") as f:
        f.write(keyfile_content)

    fvs.load_keyfile(keyfile_to_run)
    fvs.run()
    assert fvs.exit_code == 0
    fvs._close()


def test_exit_code_keyword_error(tmp_path):
    fvs = FVS(TEST_DLL)
    assert fvs.exit_code == FVS_EXIT_CODE_NO_ERROR
    keyfile_content = TEST_KEYFILE_PATH.read_text()
    keyfile_to_run = tmp_path / "test_keyfile.key"
    DSNOUT = tmp_path / "FVSOut.db"  # need to specify FVSOut.db in tmp_path
    # otherwise FVS will autogenerate one to store error messages
    with open(keyfile_to_run, "w") as f:
        f.write(
            keyfile_content.replace(
                "STDIDENT", f"DATABASE\nDSNOUT\n{DSNOUT}\nEND\nSTDIDENT"
            ).replace("NUMCYCLE        10.0", "NUMCYCLE")
        )

    fvs.load_keyfile(keyfile_to_run)
    fvs.run()
    assert fvs.exit_code == FVS_EXIT_CODE_KEYWORD_ERROR
    fvs._close()


def test_exit_code_input_data_error(tmp_path):
    fvs = FVS(TEST_DLL)
    assert fvs.exit_code == FVS_EXIT_CODE_NO_ERROR
    keyfile_content = TEST_KEYFILE_PATH.read_text()
    keyfile_to_run = tmp_path / "test_keyfile.key"
    DSNOUT = tmp_path / "FVSOut.db"  # need to specify FVSOut.db in tmp_path
    # otherwise FVS will autogenerate one to store error messages
    with open(keyfile_to_run, "w") as f:
        f.write(
            keyfile_content.replace(
                "STDIDENT", f"DATABASE\nDSNOUT\n{DSNOUT}\nEND\nSTDIDENT"
            ).replace("CDS612", "ABCDEF")
        )
    fvs.load_keyfile(keyfile_to_run)
    fvs.run()
    assert fvs.exit_code == FVS_EXIT_CODE_INPUT_DATA_ERROR
    fvs._close()


def test_dims(tmp_path):
    fvs = FVS(TEST_DLL)
    assert fvs.dims == FVSSO_START_DIMS

    keyfile_content = TEST_KEYFILE_PATH.read_text()
    keyfile_to_run = tmp_path / "test_keyfile.key"

    with open(keyfile_to_run, "w") as f:
        f.write(keyfile_content)
    fvs.load_keyfile(keyfile_to_run)
    fvs.run(
        -1
    )  # run until first possible stop point (just load trees + keyfile params)
    assert fvs.dims["ntrees"] == 2
    assert fvs.dims["ncycles"] == 10
    assert fvs.dims["nplots"] == 1
    fvs._close()

    fvs = FVS(TEST_DLL.replace("FVSso", "FVSop"))
    assert fvs.dims == FVSOP_START_DIMS
    fvs._close()


def test_stand_ids(tmp_path):
    fvs = FVS(TEST_DLL)

    with pytest.raises(AttributeError, match="Keyfile not loaded yet."):
        fvs.stand_ids

    keyfile_content = TEST_KEYFILE_PATH.read_text()
    keyfile_to_run = tmp_path / "test_keyfile.key"
    with open(keyfile_to_run, "w") as f:
        f.write(keyfile_content)
    fvs.load_keyfile(keyfile_to_run)

    with pytest.raises(
        RuntimeError, match="No inventory data loaded yet. Call `run` method."
    ):
        fvs.stand_ids

    fvs.run(-1)
    assert fvs.stand_ids == SO_KEYFILE_STAND_IDS
    fvs._close()

    fvs = FVS(TEST_DLL)
    NEW_MGMT_ID = "WHAT"
    NEW_STAND_ID = "6789"
    with open(keyfile_to_run, "w") as f:
        f.write(
            keyfile_content.replace(
                "PROCESS", f"MGMTID\n{NEW_MGMT_ID}\nPROCESS"
            ).replace("12345", NEW_STAND_ID)
        )
    fvs.load_keyfile(keyfile_to_run)
    fvs.run(-1)
    assert fvs.stand_ids["mgmt_id"] == NEW_MGMT_ID
    assert fvs.stand_ids["stand_id"] == NEW_STAND_ID
    fvs._close()

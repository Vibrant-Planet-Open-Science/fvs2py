import importlib.resources

from fvs2py._base import FVS

TEST_DLL = "/usr/local/lib/FVSso.so"
TEST_KEYFILE_PATH = importlib.resources.files("fvs2py.tests.keyfiles").joinpath(
    "SO.key"
)


def test_load_keyfile():
    """Checks that keyfile attributes get populated and itrncd updates."""
    fvs = FVS(TEST_DLL)
    assert fvs.itrncd == -1
    assert fvs.keyfile is None
    assert fvs.keyfile_path is None
    fvs.load_keyfile(TEST_KEYFILE_PATH)
    assert fvs.itrncd == 0
    assert fvs.keyfile_path == TEST_KEYFILE_PATH
    assert fvs.keyfile == TEST_KEYFILE_PATH.read_text()

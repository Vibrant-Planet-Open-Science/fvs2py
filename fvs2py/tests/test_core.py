import pytest

from fvs2py.constants import NEEDED_ROUTINES
from fvs2py.core import FvsCore


@pytest.fixture
def mock_valid_fvs_dll(mocker):
    class ValidFvsDLL:
        def fvs():
            return

        def fvsAddActivity():
            return

        def fvsAddTrees():
            return

        def fvsDimSizes():
            return

        def fvsEvmonAttr():
            return

        def fvsFFEAttrs():
            return

        def fvsGetRestartCode():
            return

        def fvsGetRtnCode():
            return

        def fvsGetICCode():
            return

        def fvsSVSDimSizes():
            return

        def fvsSetStoppointCodes():
            return

        def fvsSetCmdLine():
            return

        def fvsSVSObjData():
            return

        def fvsSpeciesAttr():
            return

        def fvsSpeciesCode():
            return

        def fvsStandID():
            return

        def fvsSummary():
            return

        def fvsTreeAttr():
            return

        def fvsUnitConversion():
            return

    mock_dll_obj = mocker.MagicMock(spec=ValidFvsDLL)
    mocker.patch("ctypes.cdll.LoadLibrary", return_value=mock_dll_obj)


@pytest.fixture
def mock_invalid_fvs_dll(mocker):
    class InvalidFvsDLL:
        """We would expect a lot more functions in a valid FVS DLL."""

        def fvs():
            return

    mock_dll_obj = mocker.MagicMock(spec=InvalidFvsDLL)
    mocker.patch("ctypes.cdll.LoadLibrary", return_value=mock_dll_obj)


@pytest.fixture
def mock_another_invalid_fvs_dll(mocker):
    class InvalidFvsDLL:
        """We expect all needed routines to be callable, not attributes."""

        def __init__(self):
            self.fvs = None  # expected function is an attribute, not callable

    mock_dll_obj = mocker.MagicMock(spec=InvalidFvsDLL)
    mocker.patch("ctypes.cdll.LoadLibrary", return_value=mock_dll_obj)


@pytest.fixture
def mock_valid_reformatted_fvs_dll(mocker):
    class ValidFvsDLL:
        def fvs_():
            return

        def fvsaddactivity_():
            return

        def fvsaddtrees_():
            return

        def fvsdimsizes_():
            return

        def fvsevmonattr_():
            return

        def fvsffeattrs_():
            return

        def fvsgetrestartcode_():
            return

        def fvsgetrtncode_():
            return

        def fvsgeticcode_():
            return

        def fvssvsdimsizes_():
            return

        def fvssetstoppointcodes_():
            return

        def fvssetcmdline_():
            return

        def fvssvsobjdata_():
            return

        def fvsspeciesattr_():
            return

        def fvsspeciescode_():
            return

        def fvsstandid_():
            return

        def fvssummary_():
            return

        def fvstreeattr_():
            return

        def fvsunitconversion_():
            return

    mock_dll_obj = mocker.MagicMock(spec=ValidFvsDLL)
    mocker.patch("ctypes.cdll.LoadLibrary", return_value=mock_dll_obj)


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

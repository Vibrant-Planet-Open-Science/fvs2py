import contextlib

import pytest

from fvs2py import _core


@pytest.fixture(autouse=True)
def release_fvs_slot():
    """Close any instance a test left open, so it can't wedge the next test."""
    yield
    holder = _core._ACTIVE
    if holder is not None:
        # Mocked libraries can't be dlclosed.
        with contextlib.suppress(Exception):
            holder.close()
        _core._ACTIVE = None


@pytest.fixture
def mock_valid_fvs_dll(mocker):
    """A mocker for an FVS DLL with all expected routines as callables."""

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

        def fvsGetBuildInfo():
            return

        def fvsGetRestartCode():
            return

        def fvsGetVersion():
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

        def fvsSetMemoryTables():
            return

        def fvsTableList():
            return

        def fvsTableDims():
            return

        def fvsTableColumns():
            return

        def fvsTableNum():
            return

        def fvsTableTxt():
            return

        def fvsClearTable():
            return

    mock_dll_obj = mocker.MagicMock(spec=ValidFvsDLL)
    mocker.patch("ctypes.CDLL", return_value=mock_dll_obj)


@pytest.fixture
def mock_invalid_fvs_dll(mocker):
    """A mocker of an FVS DLL where not all expected routines exist."""

    class InvalidFvsDLL:
        """We would expect a lot more functions in a valid FVS DLL."""

        def fvs():
            return

    mock_dll_obj = mocker.MagicMock(spec=InvalidFvsDLL)
    mocker.patch("ctypes.CDLL", return_value=mock_dll_obj)


@pytest.fixture
def mock_another_invalid_fvs_dll(mocker):
    """A mocker for an FVS DLL where an expected routine is not callable."""

    class InvalidFvsDLL:
        """We expect all needed routines to be callable, not attributes."""

        def __init__(self):
            self.fvs = None  # expected function is an attribute, not callable

    mock_dll_obj = mocker.MagicMock(spec=InvalidFvsDLL)
    mocker.patch("ctypes.CDLL", return_value=mock_dll_obj)


@pytest.fixture
def mock_valid_reformatted_fvs_dll(mocker):
    """A mocker for FVS DLL with routines that have been renamed during build."""

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

        def fvsgetbuildinfo_():
            return

        def fvsgetrestartcode_():
            return

        def fvsgetversion_():
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

        def fvssetmemorytables_():
            return

        def fvstablelist_():
            return

        def fvstabledims_():
            return

        def fvstablecolumns_():
            return

        def fvstablenum_():
            return

        def fvstabletxt_():
            return

        def fvscleartable_():
            return

        def fvsunitconversion_():
            return

    mock_dll_obj = mocker.MagicMock(spec=ValidFvsDLL)
    mocker.patch("ctypes.CDLL", return_value=mock_dll_obj)

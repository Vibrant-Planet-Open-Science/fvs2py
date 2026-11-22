from __future__ import annotations

import pytest

from fvs2py import cli
from fvs2py._core import FvsCore


class FakeFVS(FvsCore):
    """Stands in for FVS: finishes after one `fvs` call with ICCode 2."""

    def __init__(self):
        self._itrncd = None
        self.itrncd = 0
        self.exit_code = 2
        self.calls = []
        self.version = "2027.1.1 (USDAForestService)"

    def _invoke(self, name, **kwargs):
        self.calls.append((name, kwargs))
        if name == "fvsGetBuildInfo":
            text = b"Version: 2027.1.1\nOrg:     USDAForestService"
            kwargs["buf"][: len(text)] = text
            return len(text)
        if name == "fvs":
            self.itrncd = 2
        return None


@pytest.fixture
def fake_fvs(mocker, tmp_path):
    lib = tmp_path / "FVSpn.so"
    lib.touch()
    fvs = FakeFVS()
    mocker.patch.object(cli, "FVS", return_value=fvs)
    # capsys replaces stderr with an object that has no fileno().
    mocker.patch.object(cli.faulthandler, "enable")
    return lib, fvs


def test_passes_fvs_args_through_and_mirrors_exit_status(fake_fvs, capsys):
    lib, fvs = fake_fvs
    status = cli.main([
        f"--lib={lib}",
        "--keywordfile=k.key",
        "--stoppoint=1,2030",
    ])
    kwargs = dict(fvs.calls)["fvsSetCmdLine"]
    assert kwargs["cmdline"] == b"--keywordfile=k.key --stoppoint=1,2030"
    assert kwargs["nch"].value == len(kwargs["cmdline"])
    assert status == 20
    assert "STOP 20" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("flag", "expected"),
    [
        ("--version", "2027.1.1 (USDAForestService)\n"),
        ("--build-info", "Version: 2027.1.1\nOrg:     USDAForestService\n"),
    ],
)
def test_version_flags_print_and_skip_the_run(fake_fvs, capsys, flag, expected):
    lib, fvs = fake_fvs
    assert cli.main([f"--lib={lib}", flag]) == 0
    assert capsys.readouterr().out == expected
    assert "fvs" not in dict(fvs.calls)


def test_missing_lib_exits_2(tmp_path):
    with pytest.raises(SystemExit) as exc:
        cli.main([f"--lib={tmp_path}/nope.so"])
    assert exc.value.code == 2


def test_variant_loads_fvs_runtime_library(fake_fvs, mocker):
    lib, _ = fake_fvs
    mocker.patch.object(cli, "runtime_library_path", return_value=lib)
    assert cli.main(["--variant=pn", "--keywordfile=k.key"]) == 20
    cli.FVS.assert_called_once_with(lib_path=lib)


def test_unknown_variant_exits_2(mocker):
    mocker.patch.object(
        cli, "runtime_library_path", side_effect=LookupError("no xx")
    )
    with pytest.raises(SystemExit) as exc:
        cli.main(["--variant=xx"])
    assert exc.value.code == 2


def test_variant_and_lib_are_exclusive(tmp_path):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--variant=pn", f"--lib={tmp_path}/FVSpn.so"])
    assert exc.value.code == 2

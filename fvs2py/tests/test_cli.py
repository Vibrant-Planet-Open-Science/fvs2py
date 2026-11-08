from __future__ import annotations

import importlib.resources
import re
import subprocess
import sys
from pathlib import Path

import pytest

from fvs2py import cli
from fvs2py.enums import FvsVariant


class FakeFVS:
    """Stands in for FVS: finishes after one `fvs` call with ICCode 2."""

    def __init__(self):
        self._itrncd = None
        self.itrncd = 0
        self.exit_code = 2
        self.calls = []

    def _invoke(self, name, **kwargs):
        self.calls.append((name, kwargs))
        if name == "fvs":
            self.itrncd = 2


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
    name, kwargs = fvs.calls[0]
    assert name == "fvsSetCmdLine"
    assert kwargs["cmdline"] == b"--keywordfile=k.key --stoppoint=1,2030"
    assert kwargs["nch"].value == len(kwargs["cmdline"])
    assert [c[0] for c in fvs.calls[1:]] == ["fvs"]
    assert status == 20
    assert "STOP 20" in capsys.readouterr().err


def test_missing_lib_exits_2(tmp_path):
    with pytest.raises(SystemExit) as exc:
        cli.main([f"--lib={tmp_path}/nope.so"])
    assert exc.value.code == 2


def _out_without_timestamps(path: Path) -> str:
    # The .out header carries the run date and time.
    text = path.read_text()
    text = re.sub(r"\d{2}-\d{2}-\d{4}", "<date>", text)
    return re.sub(r"\d{2}:\d{2}:\d{2}", "<time>", text)


def _run_both(variant: str, keyfile: str, tmp_path: Path):
    results = {}
    cmds = {
        "native": [f"/usr/local/bin/FVS{variant}"],
        "fvs2py": [
            sys.executable,
            "-m",
            "fvs2py.cli",
            f"--lib=/usr/local/lib/FVS{variant}.so",
        ],
    }
    for name, cmd in cmds.items():
        run_dir = tmp_path / name
        run_dir.mkdir()
        (run_dir / "k.key").write_text(keyfile)
        proc = subprocess.run(
            [*cmd, "--keywordfile=k.key"], capture_output=True, cwd=run_dir
        )
        results[name] = (proc, run_dir / "k.out")
    return results


@pytest.mark.parametrize("variant", [v.lower() for v in FvsVariant])
def test_matches_native_cli(variant: str, tmp_path: Path):
    keyfile = (
        importlib.resources
        .files("fvs2py.tests.keyfiles")
        .joinpath(f"{variant.upper()}.key")
        .read_text()
    )
    results = _run_both(variant, keyfile, tmp_path)
    (native, native_out), (ours, our_out) = results.values()
    assert ours.returncode == native.returncode == 0
    assert ours.stdout == native.stdout
    assert _out_without_timestamps(our_out) == _out_without_timestamps(
        native_out
    )


def test_keyword_error_matches_native_cli(tmp_path: Path):
    keyfile = "NOTAKEYWD\nPROCESS\nSTOP\n"
    results = _run_both("pn", keyfile, tmp_path)
    (native, _), (ours, _) = results.values()
    assert native.returncode != 0
    assert ours.returncode == native.returncode

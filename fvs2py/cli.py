"""The `fvs` command, a drop-in for the `FVS<variant>` executables.

These two commands do the same thing:

    FVSpn --keywordfile=name.key
    fvs --variant=pn --keywordfile=name.key

`--variant` loads the library from fvs-runtime (`pip install
'fvs2py[runtime]'`); `--lib=/path/to/FVSpn.so` loads any other. Every other
argument is passed straight to FVS. The exit status matches the FVS executables:
0 on success, otherwise 10 times the FVS error code. As with the executables, a
first FVS argument of `--version` or `--build-info` prints that and exits.

Run `fvs` as a subprocess to survive FVS crashes and capture its output.
"""

from __future__ import annotations

import argparse
import faulthandler
import os
import sys

from fvs2py import _calls
from fvs2py._base import FVS
from fvs2py._core import runtime_library_path
from fvs2py.enums import FvsItrnCode


def main(argv: list[str] | None = None) -> int:
    """Run FVS with CLI semantics and return the process exit status.

    Args:
        argv: Command-line arguments, excluding the program name. Defaults to
            `sys.argv[1:]`.

    Returns:
        `0` on success, otherwise `10 * fvsGetICCode` like the FVS CLI.
    """
    parser = argparse.ArgumentParser(
        prog="fvs",
        description=(
            "Run FVS through fvs2py. Arguments other than --variant and --lib "
            "are passed to FVS unchanged."
        ),
        allow_abbrev=False,
    )
    lib_group = parser.add_mutually_exclusive_group(required=True)
    lib_group.add_argument(
        "--variant", help="FVS variant to load from fvs-runtime, e.g. pn"
    )
    lib_group.add_argument("--lib", help="path to the FVS shared library")
    args, fvs_args = parser.parse_known_args(argv)

    if args.variant:
        try:
            lib = runtime_library_path(args.variant)
        except (ImportError, LookupError) as e:
            parser.error(str(e))
    elif os.path.isfile(args.lib):
        lib = args.lib
    else:
        parser.error(f"--lib {args.lib!r} does not exist")

    # Python traceback on SIGSEGV/SIGFPE/SIGABRT; the signal is re-raised so the
    # parent still sees a negative return code.
    faulthandler.enable()
    # Must be set before libgfortran initializes (on library load), or output
    # buffered just before a crash is lost.
    os.environ.setdefault("GFORTRAN_UNBUFFERED_PRECONNECTED", "y")

    fvs = FVS(lib_path=lib)

    if fvs_args[:1] == ["--version"]:
        sys.stdout.write(f"{fvs.version}\n")
        return 0
    if fvs_args[:1] == ["--build-info"]:
        # FVS's own text, not `fvs.build_info`, to match the executables exactly.
        text = _calls._read_text(fvs._invoke, "fvsGetBuildInfo", 512)
        sys.stdout.write(f"{text}\n")
        return 0

    fvs._set_cmdline(" ".join(fvs_args))
    while fvs.itrncd == FvsItrnCode.GOOD_RUNNING_STATE:
        fvs._invoke("fvs", itrncd=fvs._itrncd)

    status = 10 * fvs.exit_code
    if status:
        sys.stderr.write(f"STOP {status}\n")
    return status


if __name__ == "__main__":
    sys.exit(main())

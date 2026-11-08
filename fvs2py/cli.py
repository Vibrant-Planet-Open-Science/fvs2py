"""The `fvs` command, a drop-in for the `FVS<variant>` executables.

These two commands do the same thing:

    FVSpn --keywordfile=name.key
    fvs --lib=/usr/local/lib/FVSpn.so --keywordfile=name.key

Every argument other than `--lib` is passed straight to FVS. The exit status matches the FVS executables: 0 on success, otherwise
10 times the FVS error code.

Run `fvs` as a subprocess to survive FVS crashes and capture its output.
"""

from __future__ import annotations

import argparse
import ctypes as ct
import faulthandler
import os
import sys

from fvs2py._base import FVS
from fvs2py.enums import FvsItrnCode


def main(argv: list[str] | None = None) -> int:
    """Run FVS with CLI semantics and return the process exit status.

    Args:
        argv: Command-line arguments, excluding the program name. Defaults
            to `sys.argv[1:]`.

    Returns:
        `0` on success, otherwise `10 * fvsGetICCode` like the FVS CLI.
    """
    parser = argparse.ArgumentParser(
        prog="fvs",
        description=(
            "Run FVS through fvs2py. Arguments other than --lib are passed "
            "to FVS unchanged."
        ),
        allow_abbrev=False,
    )
    parser.add_argument(
        "--lib", required=True, help="path to the FVS shared library"
    )
    args, fvs_args = parser.parse_known_args(argv)

    if not os.path.isfile(args.lib):
        parser.error(f"--lib {args.lib!r} does not exist")

    # Python traceback on SIGSEGV/SIGFPE/SIGABRT; the signal is re-raised so
    # the parent still sees a negative return code.
    faulthandler.enable()
    # Must be set before libgfortran initializes (on library load), or
    # output buffered just before a crash is lost.
    os.environ.setdefault("GFORTRAN_UNBUFFERED_PRECONNECTED", "y")

    fvs = FVS(args.lib)

    cmdline = " ".join(fvs_args).encode()
    fvs._invoke(
        "fvsSetCmdLine",
        cmdline=cmdline,
        nch=ct.c_int(len(cmdline)),
        itrncd=fvs._itrncd,
    )
    while fvs.itrncd == FvsItrnCode.GOOD_RUNNING_STATE:
        fvs._invoke("fvs", itrncd=fvs._itrncd)

    status = 10 * fvs.exit_code
    if status:
        sys.stderr.write(f"STOP {status}\n")
    return status


if __name__ == "__main__":
    sys.exit(main())

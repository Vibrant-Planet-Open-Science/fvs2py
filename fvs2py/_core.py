"""The stateful part of `FVS`: the loaded library and the run lifecycle.

Everything here either owns Python-side state that must stay in sync with the
loaded library (the handle, bound routines, keyfile, `itrncd` buffer, stop
points, registered Event Monitor names) or changes it. Stateless calls live in
`fvs2py._calls` and `fvs2py._attributes`.
"""

from __future__ import annotations

import ctypes as ct
import logging
import os
import warnings
from pathlib import Path
from typing import Any

from fvs2py._routines import FVS_ROUTINES
from fvs2py.common import load_dll, unload_dll
from fvs2py.constants import EVMON_ATTRS
from fvs2py.enums import FvsItrnCode, FvsRestartCode, FvsStopPointCode
from fvs2py.keyfile import validate_single_stand


class FvsCore:
    """Loaded FVS library plus the Python-side state kept alongside it."""

    def __init__(self, lib_path: str | os.PathLike) -> None:
        """Load the FVS shared library and bind its routines.

        Raises:
            ImportError: If any routine in `FVS_ROUTINES` is not present or not
                callable on the loaded library.
        """
        self.lib_path: Path = Path(os.path.abspath(lib_path))
        self._lib: ct.CDLL | None = None
        self._funcs: dict[str, Any] = {}
        self.variant: str = (
            os.path
            .basename(self.lib_path)
            .split(".")[0]
            .split("FVS")[-1]
            .upper()
        )
        self._load_fvs()
        self._initialize_attributes()

    def _initialize_attributes(self) -> None:
        """Reset the Python-side state kept alongside the library."""
        self.keyfile_path: Path | None = None
        self.keyfile: str | None = None
        self._itrncd = ct.c_int(-1)
        self._stop_point_code: ct.c_int | None = None
        self._stop_point_year: ct.c_int | None = None
        self._evmon_names: dict[str, None] = dict.fromkeys(EVMON_ATTRS)

    def _invoke(self, name: str, /, **kwargs: Any) -> Any:
        """Call the FVS routine `name` via its `FVS_ROUTINES` declaration.

        Every call into the native library goes through here.

        Raises:
            RuntimeError: If the library has been unloaded.
        """
        if self._lib is None:
            msg = f"FVS library not loaded, unable to call {name}."
            raise RuntimeError(msg)
        return FVS_ROUTINES[name].call(self._funcs[name], **kwargs)

    def _load_fvs(self) -> None:
        """Load the FVS shared library and bind every routine in `FVS_ROUTINES`.

        Tries the `name_` mangling first, then the un-mangled name.

        Raises:
            ImportError: If any routines are missing or not callable.
        """
        self._lib = load_dll(self.lib_path)
        missing: list[str] = []
        for name in FVS_ROUTINES:
            for candidate in (f"{name.lower()}_", name):
                func = getattr(self._lib, candidate, None)
                if callable(func):
                    logging.debug(f"Found {name} as {candidate}.")
                    self._funcs[name] = func
                    break
            else:
                missing.append(name)

        if missing:
            msg = " ".join([
                ", ".join(missing),
                "are needed routines that are not available in library, "
                "(maybe they weren't exported when library was built)",
            ])
            raise ImportError(msg)

    def _unload_fvs(self) -> None:
        """Unload the FVS shared library, if any, and drop its routines."""
        self._funcs.clear()
        if self._lib:
            unload_dll(self._lib)
            self._lib = None

    def _reload_fvs(self) -> None:
        """Unload the library, load a fresh copy, and reset Python-side state."""
        self._unload_fvs()
        self._load_fvs()
        self._initialize_attributes()

    def _set_cmdline(self, cmdline: str) -> None:
        """Pass `cmdline` to FVS as if it were the executable's arguments."""
        encoded = cmdline.encode()
        self._invoke(
            "fvsSetCmdLine",
            cmdline=encoded,
            nch=ct.c_int(len(encoded)),
            itrncd=self._itrncd,
        )

    def _require_keyfile(self, *, started: bool = False) -> None:
        """Raise `RuntimeError` unless a keyfile is loaded.

        With `started=True`, also require that `run` has been called.
        """
        if self.keyfile is None:
            msg = "No keyfile loaded yet. Call `load_keyfile` first."
            raise RuntimeError(msg)
        if started and self._stop_point_code is None:
            msg = "Simulation has not started yet. Call `run` first."
            raise RuntimeError(msg)

    def _load_keyfile(
        self, keywordfile: str | os.PathLike, *, check_single_stand: bool
    ) -> None:
        """Reset FVS if it has run, then point it at `keywordfile`."""
        itrncd = self._invoke("fvsGetRtnCode")
        if itrncd != FvsItrnCode.NOT_STARTED:
            if itrncd != FvsItrnCode.FINISHED_ALL_STANDS:
                msg = (
                    "FVS had not completed the previous simulation. "
                    "Outputs from that simulation may be incomplete."
                )
                warnings.warn(msg)
            logging.debug("FVS was already started. Resetting.")
            self._reload_fvs()

        self.keyfile_path = Path(os.path.abspath(keywordfile))
        with open(self.keyfile_path) as f:
            self.keyfile = f.read()

        if check_single_stand:
            try:
                validate_single_stand(self.keyfile)
            except ValueError as exc:
                msg = (
                    f"{exc}\n"
                    "If this keyfile is intended to describe multiple "
                    "stands, bypass this check by calling "
                    "`load_keyfile(..., check_single_stand=False)` and "
                    "drive the simulation via `FVS.run_batch()`."
                )
                raise ValueError(msg) from exc

        self._set_cmdline(f"--keywordfile={self.keyfile_path}")

    def _set_stop_point_codes(
        self, stop_point_code: int | None, stop_point_year: int | None
    ) -> None:
        """Validate, store, and send the stop point code and year to FVS."""
        if stop_point_code is not None:
            try:
                FvsStopPointCode(stop_point_code)
            except ValueError as e:
                msg = "Invalid value for stop_point_code"
                raise ValueError(msg) from e
            self._stop_point_code = ct.c_int(stop_point_code)
        elif self._stop_point_code is None:
            self._stop_point_code = ct.c_int(0)

        if stop_point_year is not None:
            if stop_point_code is not None:
                self._stop_point_year = ct.c_int(stop_point_year)
            else:
                msg = (
                    "Must specify stop_point_year if also specifying "
                    "stop_point_code"
                )
                raise ValueError(msg)
        elif self._stop_point_year is None:
            self._stop_point_year = ct.c_int(0)

        self._invoke(
            "fvsSetStoppointCodes",
            stop_point_code=self._stop_point_code,
            stop_point_year=self._stop_point_year,
        )

    def _run_batch(self, stop_point_code: int, stop_point_year: int) -> None:
        """Call `fvs` until FVS pauses at a stop point or finishes a stand."""
        self._require_keyfile()
        self._set_stop_point_codes(stop_point_code, stop_point_year)
        while self._invoke("fvsGetRtnCode") == FvsItrnCode.GOOD_RUNNING_STATE:
            self._invoke("fvs", itrncd=self._itrncd)
            if self._invoke("fvsGetRestartCode") != FvsRestartCode.INITIALIZED:
                break

    def _run(self, stop_point_code: int, stop_point_year: int) -> None:
        """`_run_batch`, then one more `fvs` call to flush a finished stand."""
        self._run_batch(stop_point_code, stop_point_year)
        if (
            self._invoke("fvsGetRestartCode")
            == FvsRestartCode.DONE_RUNNING_STAND
        ):
            self._invoke("fvs", itrncd=self._itrncd)

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
import threading
import warnings
from pathlib import Path
from typing import Any

from fvs2py import _calls
from fvs2py._routines import FVS_ROUTINES
from fvs2py.common import load_dll, unload_dll
from fvs2py.constants import EVMON_ATTRS
from fvs2py.enums import FvsItrnCode, FvsRestartCode, FvsStopPointCode
from fvs2py.keyfile import validate_single_stand

# FVS keeps its run state in process-wide Fortran globals, and on Linux every
# variant shares one libgfortran I/O unit table, so only one instance may hold a
# loaded library at a time. `_load_fvs` claims the slot; `_unload_fvs` releases.
_ACTIVE: FvsCore | None = None
# One global lock: FVS itself is not thread-safe. Reentrant because eviction
# unloads the holder under the lock.
_ACTIVE_LOCK = threading.RLock()


def _evict_or_raise(holder: FvsCore) -> None:
    """Close `holder` unless it is mid-run, in which case raise.

    A holder that has not started, has finished, or has errored is closed (with
    a warning for an error). One paused at a stop point, or at
    `DONE_RUNNING_STAND` with its output not yet flushed, is left untouched.

    Raises:
        RuntimeError: If `holder` is mid-run.
    """
    itrncd = holder._invoke("fvsGetRtnCode")
    if itrncd == FvsItrnCode.GOOD_RUNNING_STATE:
        restart = holder._invoke("fvsGetRestartCode")
        if restart != FvsRestartCode.INITIALIZED:
            stand = _calls.stand_ids(holder._invoke)["stand_id"]
            msg = (
                "Another FVS instance is still running in this process "
                f"(variant {holder.variant}, keyfile {holder.keyfile_path}, "
                f"stand {stand}, paused at {FvsRestartCode(restart).name}). "
                "FVS keeps its state in process-wide globals, so only one "
                "instance can be open at a time. Finish that run (call run() "
                "or run_batch() until itrncd is FINISHED_ALL_STANDS), or call "
                "close() on it to discard it."
            )
            raise RuntimeError(msg)
    elif itrncd == FvsItrnCode.ERROR:
        exit_code = holder._invoke("fvsGetICCode")
        msg = (
            "While creating a new FVS instance, encountered an existing one in "
            f"an error state that will now be closed (variant {holder.variant},"
            f" keyfile {holder.keyfile_path}, exit code {exit_code})."
        )
        warnings.warn(msg, stacklevel=4)
    holder._unload_fvs()


class FvsCore:
    """Loaded FVS library plus the Python-side state kept alongside it."""

    def __init__(
        self, lib_path: str | os.PathLike, *, memory_tables: bool = False
    ) -> None:
        """Load the FVS shared library and bind its routines.

        Raises:
            ImportError: If any routine in `FVS_ROUTINES` is not present or not
                callable on the loaded library.
        """
        self.lib_path: Path = Path(lib_path).resolve()
        # Not reset by `_reload_fvs`; `_load_keyfile` applies it to each fresh
        # library.
        self.memory_tables = memory_tables
        self._lib: ct.CDLL | None = None
        self._funcs: dict[str, Any] = {}
        # Parsed from the name as passed, since a resolved symlink may not
        # follow the FVS<variant> naming.
        self.variant: str = (
            Path(lib_path).name.split(".")[0].split("FVS")[-1].upper()
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
            msg = (
                f"This FVS instance (keyfile {self.keyfile_path}) is closed: "
                "another instance was opened, or close() was called. Unable "
                f"to call {name}."
            )
            raise RuntimeError(msg)
        return FVS_ROUTINES[name].call(self._funcs[name], **kwargs)

    def _load_fvs(self) -> None:
        """Load the FVS shared library and bind every routine in `FVS_ROUTINES`.

        Tries the `name_` mangling first, then the un-mangled name. Claims the
        process-wide slot, closing the previous holder first if it is idle.

        Raises:
            ImportError: If any routines are missing or not callable.
            RuntimeError: If another instance is mid-run.
        """
        global _ACTIVE
        with _ACTIVE_LOCK:
            # Evict before loading: on the same path, dlopen would hand back
            # the holder's handle and its state.
            if _ACTIVE is not None and _ACTIVE is not self:
                _evict_or_raise(_ACTIVE)
            self._bind_routines()
            _ACTIVE = self

    def _bind_routines(self) -> None:
        """Load the library and bind every routine in `FVS_ROUTINES`."""
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
        """Unload the library, if any, drop its routines, and free the slot."""
        global _ACTIVE
        with _ACTIVE_LOCK:
            if _ACTIVE is self:
                _ACTIVE = None
            self._funcs.clear()
            if self._lib:
                unload_dll(self._lib)
                self._lib = None

    def _reload_fvs(self) -> None:
        """Unload the library, load a fresh copy, and reset Python state."""
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

    def _require_keyfile(self) -> None:
        """Raise `RuntimeError` unless a keyfile is loaded."""
        if self.keyfile is None:
            msg = "No keyfile loaded yet. Call `load_keyfile` first."
            raise RuntimeError(msg)

    def _require_started(self) -> None:
        """Raise `RuntimeError` unless a keyfile is loaded and `run` called."""
        self._require_keyfile()
        if (
            self._invoke("fvsGetRtnCode") == FvsItrnCode.GOOD_RUNNING_STATE
            and self._invoke("fvsGetRestartCode") == FvsRestartCode.INITIALIZED
        ):
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

        self.keyfile_path = Path(keywordfile).resolve()
        self.keyfile = self.keyfile_path.read_text()

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

        self._invoke("fvsSetMemoryTables", on=ct.c_int(int(self.memory_tables)))
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

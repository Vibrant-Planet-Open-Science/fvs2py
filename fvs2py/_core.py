from __future__ import annotations

import ctypes as ct
import logging
import os
from pathlib import Path
from typing import Any

from fvs2py._routines import FVS_ROUTINES
from fvs2py.common import load_dll, unload_dll


class FvsCore:
    """Base class for FVS API wrapper."""

    def __init__(self, lib_path: str | os.PathLike) -> None:
        """Load the FVS shared library and bind its routines.

        Args:
            lib_path: Path to the FVS shared library.

        Raises:
            ImportError: If any routine in `FVS_ROUTINES` is not present or
                not callable on the loaded library.
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

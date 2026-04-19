from __future__ import annotations

import ctypes as ct
import logging
import os
from pathlib import Path

from fvs2py._signatures import FVS_SIGNATURES
from fvs2py.common import load_dll, unload_dll
from fvs2py.constants import NEEDED_ROUTINES


class FvsCore:
    """Base class for FVS API wrapper."""

    def __init__(self, lib_path: str | os.PathLike) -> None:
        """Load the FVS shared library and bind its needed routines.

        Resolves each routine in :data:`NEEDED_ROUTINES` from the loaded
        library, tolerating both the unix-style ``name_`` mangling and the
        un-mangled ``name`` spelling, then applies any static ctypes
        signature declared in :data:`FVS_SIGNATURES` so call sites no longer
        need to reassign ``argtypes``/``restype`` on each invocation.

        Args:
            lib_path: Path to the FVS shared library.

        Raises:
            ImportError: If one or more routines in :data:`NEEDED_ROUTINES`
                are not present or not callable on the loaded library.
        """
        self.lib_path: Path = Path(os.path.abspath(lib_path))
        self._lib: ct.CDLL | None = None
        self.variant: str = (
            os.path.basename(self.lib_path)
            .split(".")[0]
            .split("FVS")[-1]
            .upper()
        )

        # Declare function attributes with type annotations for mypy.
        # These are ctypes foreign function pointers loaded from the shared library.
        self._fvs: ct._FuncPointer
        self._fvsAddActivity: ct._FuncPointer
        self._fvsAddTrees: ct._FuncPointer
        self._fvsDimSizes: ct._FuncPointer
        self._fvsEvmonAttr: ct._FuncPointer
        self._fvsFFEAttrs: ct._FuncPointer
        self._fvsGetRestartCode: ct._FuncPointer
        self._fvsGetRtnCode: ct._FuncPointer
        self._fvsGetICCode: ct._FuncPointer
        self._fvsSVSDimSizes: ct._FuncPointer
        self._fvsSetStoppointCodes: ct._FuncPointer
        self._fvsSetCmdLine: ct._FuncPointer
        self._fvsSVSObjData: ct._FuncPointer
        self._fvsSpeciesAttr: ct._FuncPointer
        self._fvsSpeciesCode: ct._FuncPointer
        self._fvsStandID: ct._FuncPointer
        self._fvsSummary: ct._FuncPointer
        self._fvsTreeAttr: ct._FuncPointer
        self._fvsUnitConversion: ct._FuncPointer

        self._load_fvs()
        assert self._lib is not None  # to satisfy type checker

        self._resolve_routines()

    def _resolve_routines(self) -> None:
        """Bind each needed FVS routine to ``self`` and apply its signature.

        For every name in :data:`NEEDED_ROUTINES`, look up the corresponding
        foreign function on ``self._lib`` (trying the ``name_`` mangling
        first, then the un-mangled name), assign the resolved function to
        ``self._<name>``, and apply any signature declared in
        :data:`FVS_SIGNATURES`.

        Raises:
            ImportError: If any needed routines are missing or not callable.
        """
        assert self._lib is not None  # to satisfy type checker
        missing: list[str] = []
        for name in NEEDED_ROUTINES:
            func: ct._FuncPointer | None = None
            for candidate in (f"{name.lower()}_", name):
                attr = getattr(self._lib, candidate, None)
                if attr is not None and callable(attr):
                    func = attr
                    logging.debug(f"Found {name} as {candidate}.")
                    break
            if func is None:
                missing.append(name)
                continue
            sig = FVS_SIGNATURES.get(name)
            if sig is not None:
                func.argtypes = sig.argtypes
                func.restype = sig.restype
            setattr(self, f"_{name}", func)

        if missing:
            msg = " ".join(
                [
                    ", ".join(missing),
                    "are needed routines that are not available in library, "
                    "(maybe they weren't exported when library was built)",
                ]
            )
            raise ImportError(msg)

    def _load_fvs(self) -> None:
        """Load the FVS shared library into ``self._lib``, unloading any prior handle."""
        if self._lib:
            logging.debug("Unloading existing library.")
            self._unload_fvs()
        self._lib = load_dll(self.lib_path)

    def _unload_fvs(self) -> None:
        """Unload the currently held FVS shared library, if any."""
        if self._lib:
            unload_dll(self._lib)
            self._lib = None
        else:
            logging.debug("No library to unload.")

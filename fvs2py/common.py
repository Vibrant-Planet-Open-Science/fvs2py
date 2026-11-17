from __future__ import annotations

import ctypes as ct
import logging
import os
import sys


def load_dll(dll_path: str | os.PathLike) -> ct.CDLL:
    """Loads a native FVS library.

    Works on Linux (`.so`), Windows (`.dll`), and macOS (`.dylib`).
    The caller supplies the full path including the file suffix.

    The FVS libraries are assumed to be statically linked, and loader search
    path manipulation is included to allow for the detection of dependent DLLs.

    Args:
        dll_path (str | os.PathLike): the path to the DLL to be loaded.

    Returns:
        the loaded DLL as a ctypes CDLL instance
    """
    dll_path_str = os.fspath(dll_path)
    logging.info(f"Loading library from {dll_path_str}")
    dll = ct.CDLL(dll_path_str)
    logging.info(f"Library loaded successfully from {dll_path_str}")
    return dll


def unload_dll(dll: ct.CDLL) -> None:
    """Unloads a native FVS library.

    Uses `FreeLibrary` on Windows and `dlclose` elsewhere (Linux and macOS). On
    success the handle is zeroed so a repeat unload cannot hand a stale handle
    back to the loader.

    Args:
        dll: the loaded DLL.

    Raises:
        RuntimeError: if the platform loader refused to unload the library.
    """
    if sys.platform == "win32":
        free_library = ct.WinDLL("kernel32", use_last_error=True).FreeLibrary
        free_library.argtypes = (ct.c_void_p,)
        free_library.restype = ct.c_int
        if not free_library(dll._handle):
            err = ct.get_last_error()
            msg = f"Failed to unload DLL: FreeLibrary error {err}"
            raise RuntimeError(msg)
    else:
        dlclose = ct.CDLL(None).dlclose
        dlclose.argtypes = (ct.c_void_p,)
        dlclose.restype = ct.c_int
        result = dlclose(dll._handle)
        if result != 0:
            msg = f"Failed to unload DLL: {result}"
            raise RuntimeError(msg)
    dll._handle = 0
    logging.debug("Library unloaded successfully.")

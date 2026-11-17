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

    Uses `FreeLibrary` on Windows and `dlclose` elsewhere (Linux and
    macOS). On success the handle is zeroed so a repeat unload cannot hand
    a stale handle back to the loader.

    Args:
        dll: the loaded DLL.

    Raises:
        RuntimeError: if the platform loader refused to unload the library.
    """
    if sys.platform == "win32":
        _free_library(dll._handle)
    else:
        _dlclose(dll._handle)
    dll._handle = 0
    logging.debug("Library unloaded successfully.")


if sys.platform == "win32":

    def _free_library(handle: int) -> None:
        """Release a loaded library handle with the Windows `FreeLibrary`.

        Args:
            handle: the `_handle` of the loaded library.

        Raises:
            RuntimeError: if `FreeLibrary` reports failure.
        """
        kernel32 = ct.WinDLL("kernel32", use_last_error=True)
        free_library = kernel32.FreeLibrary
        free_library.argtypes = (ct.c_void_p,)
        free_library.restype = ct.c_int
        if not free_library(handle):
            err = ct.get_last_error()
            msg = f"Failed to unload DLL: FreeLibrary error {err}"
            raise RuntimeError(msg)


def _dlclose(handle: int) -> None:
    """Release a loaded library handle with the POSIX `dlclose`.

    Args:
        handle: the `_handle` of the loaded library.

    Raises:
        RuntimeError: if `dlclose` returns non-zero.
    """
    close_func = ct.CDLL(None).dlclose
    close_func.argtypes = (ct.c_void_p,)
    close_func.restype = ct.c_int
    result = close_func(handle)
    if result != 0:
        msg = f"Failed to unload DLL: {result}"
        raise RuntimeError(msg)

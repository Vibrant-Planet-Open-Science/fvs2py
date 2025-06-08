from __future__ import annotations

import ctypes as ct
import os

from fvs2py.constants import NEEDED_ROUTINES


class FvsCore:
    """Base class for FVS API wrapper."""

    def __init__(self, lib_path: str | os.PathLike):
        """Loads FVS shared library and checks to ensure needed routines exist.

        Args:
          lib_path : path to FVS library
        """
        self.lib_path = os.path.abspath(lib_path)
        self._lib = ct.cdll.LoadLibrary(self.lib_path)
        self.variant = (
            os.path.basename(self.lib_path)
            .split(".")[0]
            .split("FVS")[-1]
            .upper()
        )

        # check for needed routines that are missing
        missing = []

        # add needed routines as helper methods (prepended with "_")
        for routine in NEEDED_ROUTINES:
            if hasattr(self._lib, routine) and callable(
                getattr(self._lib, routine)
            ):
                setattr(self, f"_{routine}", getattr(self._lib, routine))
            # anticipate subroutine name changes depending upon compiler and OS
            # unix pattern on fortran functions
            elif hasattr(self._lib, f"{routine.lower()}_") and callable(
                getattr(self._lib, f"{routine.lower()}_")
            ):
                setattr(
                    self,
                    f"_{routine}",
                    getattr(self._lib, f"{routine.lower()}_"),
                )
            else:
                missing.append(routine)

        if len(missing) > 0:
            msg = " ".join(
                [
                    ", ".join(missing),
                    "are needed routines that are not available in library, "
                    "(maybe they weren't exported when library was built)",
                ]
            )
            raise ImportError(msg)

        return

import ctypes as ct
import logging
import os
from pathlib import Path

from fvs2py._core import FvsCore


class FVS(FvsCore):
    """Main class for interacting with FVS at runtime."""

    def __init__(self, lib_path: str | os.PathLike):
        super().__init__(lib_path=lib_path)

        self._itrncd = ct.c_int(-1)
        self.keyfile: str | None = None
        self.keyfile_path: Path | None = None

    @property
    def itrncd(self) -> int:
        """Returns with the current return code value in FVS.

        -1: indicates that FVS has not been started.
         0:	indicates that FVS is in good running state.
         1:	indicates that FVS has detected an error of some kind and should not
                be used until reset by specifying new input.
         2:	indicates that FVS has finished processing all the stands; new input
                can be specified.
        """
        self._fvsGetRtnCode.argtypes = [ct.POINTER(ct.c_int)]
        self._fvsGetRtnCode.restype = None

        self._fvsGetRtnCode(self._itrncd)

        return self._itrncd.value

    def load_keyfile(self, keywordfile: str | os.PathLike) -> None:
        """Sets the keywordfile as a command line argument to FVS.

        Args:
          keywordfile (str | os.PathLike): path to the FVS keyword file
        """
        self._fvsSetCmdLine.argtypes = [
            ct.c_char_p,
            ct.POINTER(ct.c_int),
            ct.POINTER(ct.c_int),
        ]
        self._fvsSetCmdLine.restype = None

        self.keyfile_path = Path(os.path.abspath(keywordfile))
        with open(self.keyfile_path) as f:
            self.keyfile = f.read()

        cmdline = f"--keywordfile={self.keyfile_path}"
        nch = len(cmdline)

        self._fvsSetCmdLine(cmdline.encode(), ct.c_int(nch), self._itrncd)
        logging.debug(f"Return code updated to {self.itrncd}")

        return

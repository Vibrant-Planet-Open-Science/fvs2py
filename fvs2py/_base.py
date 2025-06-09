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
        self._stop_point_code = None
        self._stop_point_year = None
        self._restart_code = ct.c_int(0)

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

    @property
    def restart_code(self) -> int:
        """A code indicating when FVS stopped.

          1: Stop was done just before the first call to the Event Monitor.
          2: Stop was done just after the first call to the Event Monitor.
          3: Stop was done just before the second call to the Event Monitor.
          4: Stop was done just after the second call to the Event Monitor.
          5: Stop was done after growth and mortality has been computed, but
                prior to applying them.
          6: Stop was done just before the ESTAB routines are called.
        100: Stop was done after a stand has been simulated but prior to
                starting a subsequent stand.
        """
        self._fvsGetRestartCode.argtypes = [ct.POINTER(ct.c_int)]
        self._fvsGetRestartCode.restype = None
        self._fvsGetRestartCode(self._restart_code)

        return self._restart_code.value

    @property
    def stop_point_code(self) -> int | None:
        """A code used to instruct FVS when to stop during a cycle.

        -1 : Stop at every stop location.
         0 : Never stop.
         1 : Stop just before the first call to the Event Monitor.
         2 : Stop just after the first call to the Event Monitor.
         3 : Stop just before the second call to the Event Monitor.
         4 : Stop just after the second call to the Event Monitor.
         5 : Stop after growth and mortality has been computed, but prior to
                applying them.
         6 : Stop just before the ESTAB routines are called.
         7 : Stop just after input is read but before missing values are imputed
                (tree heights and crown ratios, for example) and model
                calibration (argument stptyr is ignored).
        """
        if self._stop_point_code is not None:
            return self._stop_point_code.value
        return None

    @property
    def stop_point_year(self) -> int | None:
        """A code indicating which cycles FVS should stop at.

        0 : Never stop.
        1 : Stop at every cycle.
        YYYY : A specific year during the simulation period.
        """
        if self._stop_point_year is not None:
            return self._stop_point_year.value
        return None

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

    def set_stop_point_codes(
        self,
        stop_point_code: int | None = None,
        stop_point_year: int | None = None,
    ) -> None:
        """Sets FVS stop point codes.

        Args:
            stop_point_code (int): Optional code for when FVS should stop during
                a cycle:
               -1 : Stop at every stop location
                0 : Never stop
                1 : Stop just before the first call to the Event Monitor
                2 : Stop just after the first call to the Event Monitor
                3 : Stop just before the second call to the Event Monitor
                4 : Stop just after the second call to the Event Monitor
                5 : Stop after growth and mortality has been computed, but
                        prior to applying them
                6 : Stop just before the ESTAB routines are called
                7 : Stop just after input is read but before missing values
                        are imputed
            stop_point_year (int): Optional, years FVS should stop, options are:
                0 : Never stop
               -1 : Stop at every cycle
               YYYY : A specific year during the simulation period
        """
        self._fvsSetStoppointCodes.argtypes = [
            ct.POINTER(ct.c_int),
            ct.POINTER(ct.c_int),
        ]
        self._fvsSetStoppointCodes.restype = None

        if stop_point_code is not None:
            if stop_point_code in range(-1, 8):
                self._stop_point_code = ct.c_int(stop_point_code)  # type: ignore[assignment]
            else:
                msg = "Invalid value for stop_point_code"
                raise ValueError(msg)
        elif self._stop_point_code is None:
            self._stop_point_code = ct.c_int(0)  # type: ignore[assignment]

        if stop_point_year is not None:
            if stop_point_code is not None:
                self._stop_point_year = ct.c_int(stop_point_year)  # type: ignore[assignment]
            else:
                msg = (
                    "Must specify stop_point_year if also specifying "
                    "stop_point_code"
                )
                raise ValueError(msg)
        elif self._stop_point_year is None:
            self._stop_point_year = ct.c_int(0)  # type: ignore[assignment]

        self._fvsSetStoppointCodes(self._stop_point_code, self._stop_point_year)

        return

    def run(
        self,
        stop_point_code: int | None = None,
        stop_point_year: int | None = None,
    ) -> None:
        """Runs FVS.

        Note that stopping after the simulation of each stand in a simulation is
        done even when no stop request has been scheduled (that is, FVS will
        return at the end of each stand in a simulation even if there are no
        stop codes specified). Once a stand has been fully processed by FVS, the
        FVS `restart_code` is set to 100 and the call to run() returns.

        If there are multiple stands in a single keyfile, the simulation of the
        next stand can be triggered by calling run() again.

        The main output text file may be truncated even after the last stand has
        been simulated. To conclude FVS writing to the main output file, call
        run() one last time. The `itrncd` attribute should then change to a
        value of 2, indicating all stands have been processed.

        Args:
            stop_point_code (optional, int): when FVS should stop during a cycle:
               -1 : Stop at every stop location
                0 : Never stop
                1 : Stop just before the first call to the Event Monitor
                2 : Stop just after the first call to the Event Monitor
                3 : Stop just before the second call to the Event Monitor
                4 : Stop just after the second call to the Event Monitor
                5 : Stop after growth and mortality has been computed, but
                        prior to applying them
                6 : Stop just before the ESTAB routines are called
                7 : Stop just after input is read but before missing values
                        are imputed
            stop_point_year (optional, int): years FVS should stop, options are:
                0 : Never stop
               -1 : Stop at every cycle
               YYYY : A specific year during the simulation period
        """
        self._fvs.argtypes = [ct.POINTER(ct.c_int)]
        self._fvs.restype = None

        if self.keyfile is None:
            msg = "No keyfile loaded yet."
            raise AttributeError(msg)
        logging.debug("Found keyfile.")
        self.set_stop_point_codes(stop_point_code, stop_point_year)
        logging.debug(
            f"Set stop point codes, {stop_point_code}:{self.stop_point_code}, {stop_point_year}:{self.stop_point_year}"
        )
        while self.itrncd == 0:
            logging.debug("itrncd still zero.")
            self._fvs(self._itrncd)
            logging.debug(f"Ran _fvs routine, itrncd is {self.itrncd}")
            if self.restart_code != 0:
                logging.debug("restart code not zero... halting run.")
                break

        return

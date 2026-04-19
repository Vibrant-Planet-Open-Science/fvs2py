"""Simulation lifecycle and run-status mixin."""

from __future__ import annotations

import ctypes as ct
import logging
from collections.abc import Callable

from fvs2py.common import call_out, fvs_property


class SimulationMixin:
    """Expose FVS simulation status codes and the top-level :meth:`run` loop.

    Assumes the composed class provides the foreign-function attributes
    ``_fvs``, ``_fvsGetICCode``, ``_fvsGetRtnCode``, ``_fvsGetRestartCode``
    (resolved by :class:`fvs2py._core.FvsCore`) plus the Python-side buffers
    ``_itrncd``, ``keyfile``, and the :meth:`set_stop_point_codes` helper
    contributed by :class:`ControlMixin`.
    """

    _fvs: ct._FuncPointer
    _fvsGetICCode: ct._FuncPointer
    _fvsGetRtnCode: ct._FuncPointer
    _fvsGetRestartCode: ct._FuncPointer
    _itrncd: ct.c_int
    keyfile: str | None
    stop_point_code: int | None
    stop_point_year: int | None
    set_stop_point_codes: Callable[..., None]

    @fvs_property
    def exit_code(self) -> int:
        """Gets the integer code returned when FVS exits.

        Possible values are:
          0 - No serious errors occurred.
          1 - Input data error.
          2 - Keyword or expression error.
          3 - Extension or group activities error.
          4 - Scratch file error.
        """
        return call_out(self._fvsGetICCode)

    @fvs_property
    def itrncd(self) -> int:
        """Returns with the current return code value in FVS.

        -1: indicates that FVS has not been started.
         0: indicates that FVS is in good running state.
         1: indicates that FVS has detected an error of some kind and should not
                be used until reset by specifying new input.
         2: indicates that FVS has finished processing all the stands; new input
                can be specified.
        """
        return call_out(self._fvsGetRtnCode)

    @fvs_property
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
        return call_out(self._fvsGetRestartCode)

    def run(
        self,
        stop_point_code: int = 0,
        stop_point_year: int = 0,
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

        Raises:
            AttributeError: If no keyfile has been loaded yet.
        """
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

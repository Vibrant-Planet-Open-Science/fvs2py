"""Simulation lifecycle and run-status mixin."""

from __future__ import annotations

import ctypes as ct
import logging
from collections.abc import Callable

from fvs2py.common import call_out, fvs_property
from fvs2py.enums import FvsItrnCode, FvsRestartCode, FvsSimulationState


class SimulationMixin:
    """Expose FVS simulation status codes and the top-level :meth:`run` loop.

    Assumes the composed class provides the foreign-function attributes
    ``_fvs``, ``_fvsGetICCode``, ``_fvsGetRtnCode``, ``_fvsGetRestartCode``
    (resolved by :class:`fvs2py._core.FvsCore`) plus the Python-side buffers
    ``_itrncd`` and ``_state``, the ``keyfile`` attribute, and the
    :meth:`set_stop_point_codes` helper contributed by :class:`ControlMixin`.
    """

    _fvs: ct._FuncPointer
    _fvsGetICCode: ct._FuncPointer
    _fvsGetRtnCode: ct._FuncPointer
    _fvsGetRestartCode: ct._FuncPointer
    _itrncd: ct.c_int
    _state: FvsSimulationState
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

    def _run_cycles(self) -> None:
        """Advance FVS until the current stand pauses or reaches stand-done.

        Shared inner loop used by both :meth:`run` and :meth:`run_batch`: call
        ``_fvs`` while FVS reports a good running state, breaking out the
        moment ``restart_code`` leaves ``INITIALIZED`` (either a stop-point
        pause or the ``DONE_RUNNING_STAND`` marker).
        """
        while self.itrncd == FvsItrnCode.GOOD_RUNNING_STATE:
            logging.debug("itrncd in GOOD_RUNNING_STATE.")
            self._fvs(self._itrncd)
            logging.debug(f"Ran _fvs routine, itrncd is {self.itrncd}")
            if self.restart_code != FvsRestartCode.INITIALIZED:
                logging.debug("restart code non-zero, halting run loop.")
                break

    def run(
        self,
        stop_point_code: int = 0,
        stop_point_year: int = 0,
    ) -> None:
        """Run a single-stand FVS simulation to completion.

        The call stays eager: when the stand finishes (FVS reports
        ``restart_code == FvsRestartCode.DONE_RUNNING_STAND``), :meth:`run`
        issues one additional ``_fvs`` call to flush the main output file
        before returning, so callers do not need to invoke :meth:`run` a
        second time just to finalize output. When ``stop_point_code`` pauses
        the simulation mid-cycle, no flush is performed and the next call to
        :meth:`run` resumes from the stop.

        Multi-stand keyfiles are out of scope here; use :meth:`run_batch`
        (and load the keyfile with ``check_single_stand=False``) when the
        keyfile defines more than one stand.

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
            RuntimeError: If another :meth:`run` call is already in progress
                on this instance.
        """
        if self.keyfile is None:
            msg = "No keyfile loaded yet."
            raise AttributeError(msg)
        if self._state == FvsSimulationState.RUNNING:
            msg = "Simulation already in progress."
            raise RuntimeError(msg)
        logging.debug("Found keyfile.")
        self.set_stop_point_codes(stop_point_code, stop_point_year)
        logging.debug(
            f"Set stop point codes, {stop_point_code}:{self.stop_point_code}, "
            f"{stop_point_year}:{self.stop_point_year}"
        )
        self._state = FvsSimulationState.RUNNING
        try:
            self._run_cycles()
            if self.restart_code == FvsRestartCode.DONE_RUNNING_STAND:
                logging.debug("Stand complete; flushing output.")
                self._fvs(self._itrncd)
            self._state = FvsSimulationState.COMPLETE
        except Exception:
            self._state = FvsSimulationState.ERROR
            raise

    def run_batch(
        self,
        stop_point_code: int = 0,
        stop_point_year: int = 0,
    ) -> None:
        """Advance FVS one stand's worth of cycles without auto-flushing.

        Unlike :meth:`run`, this method does not follow a ``DONE_RUNNING_STAND``
        restart code with a flush call. It simply returns once FVS either
        pauses at a stop point or reports the stand-done marker, leaving
        output finalization, stand-advance, and termination detection
        (``itrncd == FvsItrnCode.FINISHED_ALL_STANDS``) in the caller's
        hands. This is the low-level building block for driving multi-stand
        keyfiles, where the caller typically loops::

            fvs.load_keyfile(path, check_single_stand=False)
            while fvs.itrncd != FvsItrnCode.FINISHED_ALL_STANDS:
                fvs.run_batch()
                # optionally inspect per-stand outputs here

        Stop-point semantics are identical to :meth:`run`: pass non-zero
        ``stop_point_code`` / ``stop_point_year`` to pause mid-cycle, then
        call :meth:`run_batch` again to resume.

        Args:
            stop_point_code (optional, int): when FVS should stop during a
                cycle. See :meth:`run` for the full list of values.
            stop_point_year (optional, int): year(s) at which FVS should
                stop. See :meth:`run` for the full list of values.

        Raises:
            AttributeError: If no keyfile has been loaded yet.
            RuntimeError: If another run is already in progress on this
                instance.
        """
        if self.keyfile is None:
            msg = "No keyfile loaded yet."
            raise AttributeError(msg)
        if self._state == FvsSimulationState.RUNNING:
            msg = "Simulation already in progress."
            raise RuntimeError(msg)
        self.set_stop_point_codes(stop_point_code, stop_point_year)
        self._state = FvsSimulationState.RUNNING
        try:
            self._run_cycles()
            self._state = FvsSimulationState.COMPLETE
        except Exception:
            self._state = FvsSimulationState.ERROR
            raise

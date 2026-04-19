"""Keyfile-loading and stop-point control mixin."""

from __future__ import annotations

import ctypes as ct
import logging
import os
import warnings
from collections.abc import Callable
from pathlib import Path

from fvs2py.enums import FvsItrnCode, FvsStopPointCode
from fvs2py.keyfile import validate_single_stand


class ControlMixin:
    """Expose keyfile loading and stop-point configuration.

    Assumes the composed class provides ``_fvsSetCmdLine`` and
    ``_fvsSetStoppointCodes`` (resolved by :class:`fvs2py._core.FvsCore`),
    the ``_itrncd`` buffer, and the ``_stop_point_code``/``_stop_point_year``
    slots initialized by ``FVS._initialize_attributes``. :meth:`run` on
    :class:`SimulationMixin` is expected to call into
    :meth:`set_stop_point_codes`.
    """

    _fvsSetCmdLine: ct._FuncPointer
    _fvsSetStoppointCodes: ct._FuncPointer
    _itrncd: ct.c_int
    _stop_point_code: ct.c_int | None
    _stop_point_year: ct.c_int | None
    keyfile_path: Path | None
    keyfile: str | None
    itrncd: int
    _reload_fvs: Callable[[], None]

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

    def load_keyfile(
        self,
        keywordfile: str | os.PathLike,
        *,
        check_single_stand: bool = True,
    ) -> None:
        """Set the keywordfile as a command-line argument to FVS.

        If ``check_single_stand`` is true (the default), the keyfile text is
        first passed to :func:`fvs2py.keyfile.validate_single_stand`; a keyfile
        that describes zero or multiple stands raises :class:`ValueError`
        before FVS is invoked. Callers driving multi-stand runs via
        :meth:`FVS.run_batch` must set ``check_single_stand=False`` to bypass
        the guard.

        Args:
            keywordfile: Path to the FVS keyword file.
            check_single_stand: When true (default), require the keyfile to define
                exactly one stand (one each of ``STDIDENT``, ``PROCESS``,
                and ``STOP``).

        Raises:
            ValueError: If ``check_single_stand`` is true and the keyfile
                fails :func:`fvs2py.keyfile.validate_single_stand`.
        """
        if self.itrncd != FvsItrnCode.NOT_STARTED:
            if self.itrncd != FvsItrnCode.FINISHED_ALL_STANDS:
                msg = (
                    "FVS had not completed the previous simulation. "
                    "Outputs from that simulation may be incomplete."
                )
                warnings.warn(msg)
            logging.debug("FVS was already started. Resetting.")
            self._reload_fvs()

        self.keyfile_path = Path(os.path.abspath(keywordfile))
        with open(self.keyfile_path) as f:
            self.keyfile = f.read()

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

        cmdline = f"--keywordfile={self.keyfile_path}"
        nch = len(cmdline)

        self._fvsSetCmdLine(cmdline.encode(), ct.c_int(nch), self._itrncd)
        logging.debug(f"Return code updated to {self.itrncd}")

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

        Raises:
            ValueError: If ``stop_point_code`` is outside the range ``[-1, 7]``,
                or if ``stop_point_year`` is provided without ``stop_point_code``.
        """
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

        self._fvsSetStoppointCodes(self._stop_point_code, self._stop_point_year)

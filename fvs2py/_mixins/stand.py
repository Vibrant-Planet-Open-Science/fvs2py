"""Stand identification, dimensions, and summary mixin."""

from __future__ import annotations

import ctypes as ct

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from fvs2py.common import call_out, fvs_property
from fvs2py.constants import (
    MGMT_ID_COLUMN_NAME,
    STAND_CN_COLUMN_NAME,
    STAND_ID_COLUMN_NAME,
    STR_C_CONTIGUOUS,
    STR_MAXCYCLES,
    STR_MAXPLOTS,
    STR_MAXSPECIES,
    STR_MAXTREES,
    STR_NCYCLES,
    STR_NPLOTS,
    STR_NTREES,
    SUMMARY_COLS,
)


class StandMixin:
    """Expose stand-level FVS outputs: dimensions, identifiers, summary table.

    Assumes the composed class provides the foreign-function attributes
    ``_fvsDimSizes``, ``_fvsStandID``, ``_fvsSummary`` (resolved by
    :class:`fvs2py._core.FvsCore`) and the Python-side buffers ``_stand_id``,
    ``_stand_cn``, ``_mgmt_id`` (initialized by
    ``FVS._initialize_attributes``). ``keyfile`` and ``stop_point_code``
    come from :class:`ControlMixin`.
    """

    _fvsDimSizes: ct._FuncPointer
    _fvsStandID: ct._FuncPointer
    _fvsSummary: ct._FuncPointer
    _stand_id: ct.Array[ct.c_char]
    _stand_cn: ct.Array[ct.c_char]
    _mgmt_id: ct.Array[ct.c_char]
    keyfile: str | None
    stop_point_code: int | None

    @fvs_property
    def dims(self) -> dict:
        """Return the max dimensions of important FVS data storage."""
        ntrees, ncycles, nplots, maxtrees, maxspecies, maxplots, maxcycles = (
            call_out(self._fvsDimSizes, out_types=(ct.c_int,) * 7)
        )
        return {
            STR_NTREES: ntrees,
            STR_NCYCLES: ncycles,
            STR_NPLOTS: nplots,
            STR_MAXTREES: maxtrees,
            STR_MAXSPECIES: maxspecies,
            STR_MAXPLOTS: maxplots,
            STR_MAXCYCLES: maxcycles,
        }

    @fvs_property
    def stand_ids(self) -> dict:
        """Return stand identification codes.

        Raises:
            AttributeError: If no keyfile has been loaded.
            RuntimeError: If inventory data has not yet been loaded (i.e.
                :meth:`run` has not been called).
        """
        if self.keyfile is None:
            msg = "Keyfile not loaded yet."
            raise AttributeError(msg)
        if self.stop_point_code is None:
            msg = "No inventory data loaded yet. Call `run` method."
            raise RuntimeError(msg)

        self._fvsStandID(
            self._stand_id,
            self._stand_cn,
            self._mgmt_id,
            ct.c_int(0),
            ct.c_int(0),
            ct.c_int(0),
        )

        return {
            STAND_ID_COLUMN_NAME: self._stand_id.value.decode().strip(),
            STAND_CN_COLUMN_NAME: self._stand_cn.value.decode().strip(),
            MGMT_ID_COLUMN_NAME: self._mgmt_id.value.decode().strip(),
        }

    @fvs_property
    def summary(self) -> pd.DataFrame | None:
        """Return a dataframe with FVS Summary Statistics for all initiated cycles.

        The returned dataframe omits cycles that have not yet been initiated, which are
        identifiable where all values in that row are zero.
        """
        self._fvsSummary.argtypes = [
            np.ctypeslib.ndpointer(np.intc, flags=STR_C_CONTIGUOUS),  # type: ignore[arg-type]
            ct.POINTER(ct.c_int),
            ct.POINTER(ct.c_int),
            ct.POINTER(ct.c_int),
            ct.POINTER(ct.c_int),
            ct.POINTER(ct.c_int),
        ]
        self._fvsSummary.restype = None

        dims = self.dims
        if dims[STR_NCYCLES] == 0:
            return None
        summary = np.zeros(
            dtype=np.intc,
            shape=(dims[STR_NCYCLES] + 1, len(SUMMARY_COLS)),
        )
        for i in range(dims[STR_NCYCLES] + 1):
            self._fvsSummary(
                summary[i],
                ct.c_int(i + 1),  # icycle
                ct.c_int(dims[STR_NCYCLES]),  # ncycles
                ct.c_int(0),  # maxrow
                ct.c_int(0),  # maxcol
                ct.c_int(0),  # rtncode
            )

        empty_years = (summary == 0).all(axis=1)
        return pd.DataFrame(
            summary[~empty_years, :], columns=SUMMARY_COLS
        ).copy()

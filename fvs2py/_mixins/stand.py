"""Stand identification, dimensions, and summary mixin."""

from __future__ import annotations

import ctypes as ct
from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

from fvs2py.common import fvs_property
from fvs2py.constants import (
    MGMT_ID_COLUMN_NAME,
    STAND_CN_COLUMN_NAME,
    STAND_ID_COLUMN_NAME,
    STR_NCYCLES,
    SUMMARY_COLS,
)


class StandMixin:
    """Expose stand-level FVS outputs: dimensions, identifiers, summary table.

    Assumes the composed class provides :meth:`FvsCore._invoke` for registry
    dispatch and the Python-side buffers ``_stand_id``, ``_stand_cn``,
    ``_mgmt_id`` (initialized by ``FVS._initialize_attributes``). ``keyfile``
    and ``stop_point_code`` come from :class:`ControlMixin`.
    """

    _invoke: Callable[..., Any]
    _stand_id: ct.Array[ct.c_char]
    _stand_cn: ct.Array[ct.c_char]
    _mgmt_id: ct.Array[ct.c_char]
    keyfile: str | None
    stop_point_code: int | None

    @fvs_property
    def dims(self) -> dict:
        """Return the max dimensions of important FVS data storage."""
        return self._invoke("fvsDimSizes")

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

        self._invoke(
            "fvsStandID",
            stand_id=self._stand_id,
            stand_cn=self._stand_cn,
            mgmt_id=self._mgmt_id,
            stand_id_len=ct.c_int(0),
            stand_cn_len=ct.c_int(0),
            mgmt_id_len=ct.c_int(0),
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
        dims = self.dims
        if dims[STR_NCYCLES] == 0:
            return None
        summary = np.zeros(
            dtype=np.intc,
            shape=(dims[STR_NCYCLES] + 1, len(SUMMARY_COLS)),
        )
        for i in range(dims[STR_NCYCLES] + 1):
            self._invoke(
                "fvsSummary",
                summary=summary[i],
                icycle=ct.c_int(i + 1),
                ncycles=ct.c_int(dims[STR_NCYCLES]),
                maxrow=ct.c_int(0),
                maxcol=ct.c_int(0),
            )

        empty_years = (summary == 0).all(axis=1)
        return pd.DataFrame(
            summary[~empty_years, :], columns=SUMMARY_COLS
        ).copy()

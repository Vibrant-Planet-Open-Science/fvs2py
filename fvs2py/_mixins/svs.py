"""SVS/FFE API: `fvsSVSDimSizes`, `fvsSVSObjData`, and `fvsFFEAttrs`."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

from fvs2py._attributes import FFE, SVS_OBJECTS
from fvs2py.constants import (
    STR_MAXSPECIES,
    STR_NCWDOBJS,
    STR_NDEADOBJS,
    STR_NSVSOBJS,
    SVS_CWD_OBJ_ATTRS,
    SVS_LIVE_OBJ_ATTRS,
    SVS_SNAG_OBJ_ATTRS,
)


class SVSMixin:
    """Stand Visualization System and related FFE per-species schedules.

    This mixin groups FVS entry points used for 3D/SVS object geometry and
    the Fire and Fuels Extension per-species snag crown fall-year vectors
    (`fallyrs0`..`fallyrs5` via `fvsFFEAttrs`). FFE *stand-level*
    compute variables (e.g. `torchidx`, `crbaseht`) remain in
    `fvs2py._mixins.events.EventMixin` and `fvsEvmonAttr`.

    Assumes the composed class provides `FvsCore._invoke` and `dims`
    from `StandMixin`.
    """

    _invoke: Callable[..., Any]
    dims: dict

    @property
    def svs_dim_sizes(self) -> dict[str, int]:
        """Current and max SVS object counts from `fvsSVSDimSizes`.

        Keys: `nsvsobjs`, `ndeadobjs`, `ncwdobjs` (current counts) and
        `mxsvsobjs`, `mxdeadobjs`, `mxcwdobjs` (capacity).
        """
        return self._invoke("fvsSVSDimSizes")

    @property
    def ffe_attrs(self) -> pd.DataFrame:
        """DataFrame of per-species `fallyrs0`..`fallyrs5` (`fvsFFEAttrs`)."""
        return FFE.frame(self._invoke, self.dims[STR_MAXSPECIES])

    def get_ffe_attr(self, attr: str) -> npt.NDArray[np.float64]:
        """Get one `fvsFFEAttrs` fallyrs column (shape `(maxspecies,)`)."""
        return FFE.get(self._invoke, attr, self.dims[STR_MAXSPECIES])

    def set_ffe_attr(self, attr: str, arr: npt.NDArray[np.float64]) -> None:
        """Set one `fvsFFEAttrs` fallyrs column (shape `(maxspecies,)`)."""
        FFE.set(self._invoke, attr, arr, self.dims[STR_MAXSPECIES])

    def get_svs_obj_attr(self, attr: str) -> npt.NDArray[np.float64]:
        """Get one `fvsSVSObjData` array (length = current nsvs/ndead/ncwd)."""
        return SVS_OBJECTS.get(self._invoke, attr, self._svs_nobjs(attr))

    def set_svs_obj_attr(self, attr: str, arr: npt.NDArray[np.float64]) -> None:
        """Set one `fvsSVSObjData` array; shape must match current count."""
        SVS_OBJECTS.set(self._invoke, attr, arr, self._svs_nobjs(attr))

    def _svs_nobjs(self, attr: str) -> int:
        """Current object count for the SVS object kind `attr` belongs to."""
        if attr in SVS_LIVE_OBJ_ATTRS:
            key = STR_NSVSOBJS
        elif attr in SVS_SNAG_OBJ_ATTRS:
            key = STR_NDEADOBJS
        elif attr in SVS_CWD_OBJ_ATTRS:
            key = STR_NCWDOBJS
        else:
            msg = f"unrecognized SVS object attribute: {attr!r}"
            raise NameError(msg)
        return self.svs_dim_sizes[key]

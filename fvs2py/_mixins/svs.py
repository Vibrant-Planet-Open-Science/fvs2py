"""SVS/FFE API: ``fvsSVSDimSizes``, ``fvsSVSObjData``, and ``fvsFFEAttrs``."""

from __future__ import annotations

import ctypes as ct
import warnings
from collections.abc import Callable
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

from fvs2py.common import fvs_property
from fvs2py.constants import (
    STR_MAXSPECIES,
    STR_NCWDOBJS,
    STR_NDEADOBJS,
    STR_NSVSOBJS,
    SVS_CWD_OBJ_ATTRS,
    SVS_LIVE_OBJ_ATTRS,
    SVS_SNAG_OBJ_ATTRS,
)
from fvs2py.enums import FvsAttributeAccessor


def _svs_nobjs_key(attr: str) -> str:
    if attr in SVS_LIVE_OBJ_ATTRS:
        return STR_NSVSOBJS
    if attr in SVS_SNAG_OBJ_ATTRS:
        return STR_NDEADOBJS
    if attr in SVS_CWD_OBJ_ATTRS:
        return STR_NCWDOBJS
    msg = f"unrecognized SVS object attribute: {attr!r}"
    raise NameError(msg)


class SVSMixin:
    """Stand Visualization System and related FFE per-species schedules.

    This mixin groups FVS entry points used for 3D/SVS object geometry and
    the Fire and Fuels Extension per-species snag crown fall-year vectors
    (``fallyrs0``..``fallyrs5`` via ``fvsFFEAttrs``). FFE *stand-level*
    compute variables (e.g. ``torchidx``, ``crbaseht``) remain in
    :class:`fvs2py._mixins.events.EventMixin` and ``fvsEvmonAttr``.

    Assumes the composed class provides :meth:`FvsCore._invoke`, ``dims``
    from :class:`StandMixin`, and buffers ``_ffe_attrs`` and
    ``_svs_obj_attrs`` from ``FVS._initialize_attributes``.
    """

    _invoke: Callable[..., Any]
    _ffe_attrs: dict[str, npt.NDArray[np.float64] | None]
    _svs_obj_attrs: dict[str, npt.NDArray[np.float64] | None]
    dims: dict

    @fvs_property
    def svs_dim_sizes(self) -> dict[str, int]:
        """Current and max SVS object counts from ``fvsSVSDimSizes``.

        Keys: ``nsvsobjs``, ``ndeadobjs``, ``ncwdobjs`` (current counts) and
        ``mxsvsobjs``, ``mxdeadobjs``, ``mxcwdobjs`` (capacity).
        """
        return self._invoke("fvsSVSDimSizes")

    @fvs_property
    def ffe_attrs(self) -> pd.DataFrame:
        """DataFrame of per-species ``fallyrs0``..``fallyrs5`` (``fvsFFEAttrs``)."""
        for attr in self._ffe_attrs:
            _ = self.get_ffe_attr(attr)

        attrs = pd.DataFrame(self._ffe_attrs, copy=False)
        if (attrs == 0).all().all():
            warnings.warn(
                "No FFE fallyrs attributes initialized yet. "
                "Is the Fire and Fuels Extension active in the loaded keyfile?"
            )
            return attrs.replace(0, None)

        return attrs

    def get_ffe_attr(self, attr: str) -> npt.NDArray[np.float64]:
        """Get one ``fvsFFEAttrs`` fallyrs column (shape ``(maxspecies,)``)."""
        self._ffe_attr(attr, FvsAttributeAccessor.GET)
        return self._ffe_attrs[attr]

    def set_ffe_attr(self, attr: str, arr: npt.NDArray[np.float64]) -> None:
        """Set one ``fvsFFEAttrs`` fallyrs column (shape ``(maxspecies,)``)."""
        return self._ffe_attr(attr, FvsAttributeAccessor.SET, arr)

    def get_svs_obj_attr(self, attr: str) -> npt.NDArray[np.float64]:
        """Get one ``fvsSVSObjData`` array (length = current nsvs/ndead/ncwd)."""
        self._svs_obj_attr(attr, FvsAttributeAccessor.GET)
        return self._svs_obj_attrs[attr]

    def set_svs_obj_attr(self, attr: str, arr: npt.NDArray[np.float64]) -> None:
        """Set one ``fvsSVSObjData`` array; shape must match current count."""
        return self._svs_obj_attr(attr, FvsAttributeAccessor.SET, arr)

    def _ffe_attr(
        self,
        attr: str,
        action: FvsAttributeAccessor,
        arr: npt.NDArray[np.float64] | None = None,
    ) -> None:
        if attr not in self._ffe_attrs:
            msg = "Invalid variable requested. Valid options are"
            raise NameError(msg, tuple(self._ffe_attrs))

        dims = self.dims
        if action == FvsAttributeAccessor.GET and self._ffe_attrs[attr] is None:
            self._ffe_attrs[attr] = np.empty(
                dtype=np.float64, shape=(dims[STR_MAXSPECIES],)
            )
        elif action == FvsAttributeAccessor.SET:
            if arr is None:
                msg = "Must provide `arr` if `action` is 'set'"
                raise TypeError(msg)
            if arr.shape != (dims[STR_MAXSPECIES],):
                msg = (
                    "`arr` must be same shape as `maxspecies` "
                    f"({dims[STR_MAXSPECIES]},)"
                )
                raise ValueError(msg)
            self._ffe_attrs[attr] = arr

        self._invoke(
            "fvsFFEAttrs",
            attr_name=ct.c_char_p(attr.encode()),
            nch=ct.c_int(len(attr)),
            action=ct.c_char_p(action.encode()),
            maxspecies=ct.c_int(dims[STR_MAXSPECIES]),
            arr=self._ffe_attrs[attr],
        )

    def _svs_obj_attr(
        self,
        attr: str,
        action: FvsAttributeAccessor,
        arr: npt.NDArray[np.float64] | None = None,
    ) -> None:
        if attr not in self._svs_obj_attrs:
            msg = "Invalid variable requested. Valid options are"
            raise NameError(msg, self._svs_obj_attrs)

        nkey = _svs_nobjs_key(attr)
        n = int(self.svs_dim_sizes[nkey])
        if action == FvsAttributeAccessor.SET:
            if arr is None:
                msg = "Must provide `arr` if `action` is 'set'"
                raise TypeError(msg)
            if arr.shape != (n,):
                msg = f"`arr` must have shape `({n},)` for {attr!r}."
                raise ValueError(msg)
            self._svs_obj_attrs[attr] = arr
        else:
            self._svs_obj_attrs[attr] = np.empty(dtype=np.float64, shape=(n,))

        self._invoke(
            "fvsSVSObjData",
            attr_name=ct.c_char_p(attr.encode()),
            nch=ct.c_int(len(attr)),
            action=ct.c_char_p(action.encode()),
            nobjs=ct.c_int(n),
            arr=self._svs_obj_attrs[attr],
        )

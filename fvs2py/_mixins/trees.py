"""Tree-level attribute access and bulk tree insertion mixin."""

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
    ADD_TREES_COLS,
    STR_MAXTREES,
    STR_NPLOTS,
    STR_NTREES,
)
from fvs2py.enums import FvsAttributeAccessor


class TreesMixin:
    """Expose per-tree attribute access and bulk tree insertion.

    Assumes the composed class provides :meth:`FvsCore._invoke` for registry
    dispatch, ``self.dims`` from :class:`StandMixin`, ``self.species_codes``
    from :class:`SpeciesMixin`, and the ``_tree_attrs`` / ``_trees`` buffers
    seeded by ``FVS._initialize_attributes``.
    """

    _invoke: Callable[..., Any]
    _tree_attrs: tuple[str, ...]
    _trees: dict[str, npt.NDArray[np.float64] | None]
    dims: dict
    species_codes: pd.DataFrame

    @fvs_property
    def trees(self) -> pd.DataFrame | None:
        """Returns a dataframe of trees currently in FVS."""
        if self.dims[STR_NTREES] == 0:
            warnings.warn("No trees in FVS yet.")
            return None

        for attr in self._tree_attrs:
            _ = self.get_tree_attr(attr)

        return pd.DataFrame(self._trees, copy=False)

    def get_tree_attr(self, attr: str) -> npt.NDArray[np.float64]:
        """Gets a single attribute for existing trees.

        Args:
            attr (str): name of tree attribute to fetch

        Returns:
            array with values of requested attribute for all trees
        """
        self._tree_attr(attr, FvsAttributeAccessor.GET)
        return self._trees[attr]

    def set_tree_attr(self, attr: str, arr: npt.NDArray[np.float64]) -> None:
        """Sets a single attribute for all existing trees.

        Args:
            attr (str): name of tree attribute to set
            arr (npt.NDArray[np.float64]): values to set tree attribute to
        """
        return self._tree_attr(attr, FvsAttributeAccessor.SET, arr)

    def _tree_attr(
        self,
        attr: str,
        action: FvsAttributeAccessor,
        arr: npt.NDArray[np.float64] | None = None,
    ) -> None:
        """Get or set a single attribute for existing trees.

        Args:
            attr (str): attribute to set or get
            action (FvsAttributeAccessor): 'set' or 'get'
            arr (optional, npt.NDArray[np.float64]): array of values to set
        """
        if attr not in self._tree_attrs:
            self._trees[attr] = None

        ntrees = self.dims[STR_NTREES]

        if action == FvsAttributeAccessor.GET:
            self._trees[attr] = np.empty(dtype=np.float64, shape=(ntrees,))
            if ntrees == 0:
                warnings.warn("No trees in FVS yet.")
        elif action == FvsAttributeAccessor.SET:
            if arr is None:
                msg = "Must provide `arr` if `action` is 'set'"
                raise TypeError(msg)
            if arr.shape != (ntrees,):
                msg = f"`arr` must be same shape as `ntrees` ({ntrees},)"
                raise ValueError(msg)
            self._trees[attr] = arr

        self._invoke(
            "fvsTreeAttr",
            attr_name=ct.c_char_p(attr.encode()),
            nch=ct.c_int(len(attr)),
            action=ct.c_char_p(action.encode()),
            ntrees=ct.c_int(ntrees),
            arr=self._trees[attr],
        )

    def add_trees(self, tree_df: pd.DataFrame) -> None:
        """Adds trees to an existing simulation.

        Args:
            tree_df (pd.DataFrame): trees to add. Must contain every column
                listed in :data:`fvs2py.constants.ADD_TREES_COLS`
                (``dbh``, ``species``, ``ht``, ``cratio``, ``plot``, ``tpa``),
                with non-null float-coercible values for every row. Extra
                columns are ignored.
        """
        missing = tuple(c for c in ADD_TREES_COLS if c not in tree_df.columns)
        if missing:
            msg = (
                f"tree_df is missing required column(s) {list(missing)}; "
                f"expected all of {list(ADD_TREES_COLS)}"
            )
            raise ValueError(msg)

        ntrees = len(tree_df)
        trees = tree_df[list(ADD_TREES_COLS)].astype(np.float64)
        if trees.isna().any().any():
            msg = "No null values allowed in trees to add."
            raise ValueError(msg)

        dims = self.dims
        if dims[STR_MAXTREES] < dims[STR_NTREES] + ntrees:
            room = dims[STR_MAXTREES] - dims[STR_NTREES]
            msg = f"Only room for {room} new trees but {ntrees} supplied."
            raise ValueError(msg)

        if dims[STR_NPLOTS] == 0:
            msg = "No inventory plots loaded yet."
            raise RuntimeError(msg)

        if not trees["plot"].isin(range(1, dims[STR_NPLOTS] + 1)).all():
            msg = "Plot codes must be within range already defined."
            raise ValueError(msg)

        if not trees["species"].isin(self.species_codes["fvs_index"]).all():
            msg = "Unrecognized species code(s). Use FVS Species Index."
            raise ValueError(msg)

        self._invoke(
            "fvsAddTrees",
            dbh=trees["dbh"].values,
            species=trees["species"].values,
            ht=trees["ht"].values,
            cratio=trees["cratio"].values,
            plot=trees["plot"].values,
            tpa=trees["tpa"].values,
            ntrees=ct.c_int(ntrees),
        )

"""Tree-level attribute access and bulk tree insertion mixin."""

from __future__ import annotations

import ctypes as ct
import warnings
from collections.abc import Callable
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

from fvs2py._attributes import TREES
from fvs2py.constants import (
    ADD_TREES_COLS,
    STR_MAXTREES,
    STR_NPLOTS,
    STR_NTREES,
)


class TreesMixin:
    """Expose per-tree attribute access and bulk tree insertion.

    Assumes the composed class provides `FvsCore._invoke` for registry
    dispatch, `self.dims` from `StandMixin`, and `self.species_codes`
    from `SpeciesMixin`.
    """

    _invoke: Callable[..., Any]
    dims: dict
    species_codes: pd.DataFrame

    @property
    def trees(self) -> pd.DataFrame | None:
        """Returns a dataframe of trees currently in FVS."""
        ntrees = self.dims[STR_NTREES]
        if ntrees == 0:
            warnings.warn("No trees in FVS yet.")
            return None
        return TREES.frame(self._invoke, ntrees)

    def get_tree_attr(self, attr: str) -> npt.NDArray[np.float64]:
        """Gets a single attribute for existing trees.

        Args:
            attr (str): name of tree attribute to fetch

        Returns:
            a new array with the attribute's value for every tree

        Raises:
            NameError: If FVS does not recognize `attr`.
        """
        ntrees = self.dims[STR_NTREES]
        if ntrees == 0:
            warnings.warn("No trees in FVS yet.")
        return TREES.get(self._invoke, attr, ntrees)

    def set_tree_attr(self, attr: str, arr: npt.NDArray[np.float64]) -> None:
        """Sets a single attribute for all existing trees.

        Args:
            attr (str): name of tree attribute to set
            arr (npt.NDArray[np.float64]): values to set, shape `(ntrees,)`

        Raises:
            NameError: If FVS does not recognize `attr`.
            ValueError: If `arr` is not shape `(ntrees,)`.
        """
        TREES.set(self._invoke, attr, arr, self.dims[STR_NTREES])

    def add_trees(self, tree_df: pd.DataFrame) -> None:
        """Adds trees to an existing simulation.

        Args:
            tree_df (pd.DataFrame): trees to add. Must contain every column
                listed in `fvs2py.constants.ADD_TREES_COLS`
                (`dbh`, `species`, `ht`, `cratio`, `plot`, `tpa`),
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

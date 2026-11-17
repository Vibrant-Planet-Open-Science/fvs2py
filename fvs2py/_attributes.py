"""Get and set FVS's named float64 attribute arrays.

`fvsTreeAttr`, `fvsSpeciesAttr`, `fvsFFEAttrs`, `fvsSVSObjData`, and
`fvsEvmonAttr` share one calling convention: a name, a "get"/"set" action, and
a float64 array of length `n`. FVS validates the name and reports unknown names
as `NameError` through `attr_accessor_policy`.
"""

from __future__ import annotations

import ctypes as ct
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

from fvs2py.constants import (
    EVMON_ATTRS,
    FFE_FALLYRS_ATTRS,
    SPECIES_ATTRS,
    STR_MAXSPECIES,
    STR_NOBJS,
    STR_NTREES,
    SVS_OBJ_ATTRS,
    TREE_ATTRS,
)

Invoke = Callable[..., Any]


@dataclass(frozen=True, slots=True)
class AttributeTable:
    """One FVS attribute routine and the names it exposes.

    Attributes:
        routine: Registered routine name in `FVS_ROUTINES`.
        names: Canonical attribute names, used by `frame`.
        size_kwarg: Name of the routine's length parameter, if it has one.
        empty_warning: If set, `frame` warns with this message and blanks
            the frame when every value is zero (FVS has not populated it).
    """

    routine: str
    names: tuple[str, ...]
    size_kwarg: str | None = None
    empty_warning: str | None = None

    def get(self, invoke: Invoke, attr: str, n: int) -> npt.NDArray[np.float64]:
        """Return a new array holding `attr`'s current `n` values."""
        arr = np.empty(n, dtype=np.float64)
        self._call(invoke, attr, "get", arr)
        return arr

    def set(
        self, invoke: Invoke, attr: str, arr: npt.NDArray[np.float64], n: int
    ) -> None:
        """Write `arr` to `attr`.

        Raises:
            ValueError: If `arr` does not have shape `(n,)`.
        """
        if arr.shape != (n,):
            msg = f"`arr` must have shape ({n},) for {attr!r}."
            raise ValueError(msg)
        self._call(invoke, attr, "set", arr)

    def frame(self, invoke: Invoke, n: int) -> pd.DataFrame:
        """Return every name in `names` as a column."""
        df = pd.DataFrame({a: self.get(invoke, a, n) for a in self.names})
        if self.empty_warning and (df == 0).all().all():
            warnings.warn(self.empty_warning)
            return df.replace(0, None)
        return df

    def _call(
        self,
        invoke: Invoke,
        attr: str,
        action: str,
        arr: npt.NDArray[np.float64],
    ) -> None:
        size = {self.size_kwarg: ct.c_int(len(arr))} if self.size_kwarg else {}
        invoke(
            self.routine,
            attr_name=attr.encode(),
            nch=ct.c_int(len(attr)),
            action=action.encode(),
            arr=arr,
            **size,
        )


TREES = AttributeTable("fvsTreeAttr", TREE_ATTRS, size_kwarg=STR_NTREES)
SPECIES = AttributeTable(
    "fvsSpeciesAttr",
    SPECIES_ATTRS,
    empty_warning="No species attributes initialized yet.",
)
FFE = AttributeTable(
    "fvsFFEAttrs",
    FFE_FALLYRS_ATTRS,
    size_kwarg=STR_MAXSPECIES,
    empty_warning=(
        "No FFE fallyrs attributes initialized yet. "
        "Is the Fire and Fuels Extension active in the loaded keyfile?"
    ),
)
SVS_OBJECTS = AttributeTable(
    "fvsSVSObjData", SVS_OBJ_ATTRS, size_kwarg=STR_NOBJS
)
EVMON = AttributeTable("fvsEvmonAttr", EVMON_ATTRS)

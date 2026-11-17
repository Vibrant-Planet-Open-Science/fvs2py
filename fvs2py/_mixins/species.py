"""Species codes and per-species attribute access mixin."""

from __future__ import annotations

import ctypes as ct
from collections.abc import Callable
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

from fvs2py._attributes import SPECIES
from fvs2py.constants import SPECIES_COLUMN_NAMES, STR_MAXSPECIES


class SpeciesMixin:
    """Expose species metadata and per-species attribute get/set helpers.

    Assumes the composed class provides `FvsCore._invoke` for registry
    dispatch and `self.dims` from `StandMixin`.
    """

    _invoke: Callable[..., Any]
    dims: dict

    @property
    def species(self) -> pd.DataFrame:
        """Returns species codes and attributes for all species."""
        codes = self.species_codes
        attrs = self.species_attrs
        return codes.merge(attrs, left_index=True, right_index=True, copy=False)

    @property
    def species_codes(self) -> pd.DataFrame:
        """Fetch the various codes used to refer to different tree species."""
        dims = self.dims

        _fvs_spp = ct.create_string_buffer(4)
        _fia_spp = ct.create_string_buffer(4)
        _plants_spp = ct.create_string_buffer(6)

        spp_codes = pd.DataFrame(
            index=range(dims[STR_MAXSPECIES]),
            columns=SPECIES_COLUMN_NAMES,
        )

        for i in range(dims[STR_MAXSPECIES]):
            self._invoke(
                "fvsSpeciesCode",
                fvs_spp=_fvs_spp,
                fia_spp=_fia_spp,
                plants_spp=_plants_spp,
                index=ct.c_int(i + 1),
                fvs_spp_len=ct.c_int(0),
                fia_spp_len=ct.c_int(0),
                plants_spp_len=ct.c_int(0),
            )
            spp_codes.iloc[i] = (
                i + 1,
                _fvs_spp.value.decode().strip(),
                _fia_spp.value.decode().strip(),
                _plants_spp.value.decode().strip(),
            )

        return spp_codes

    @property
    def species_attrs(self) -> pd.DataFrame:
        """Returns a dataframe of species attributes.

        Fields returned are:
            spccf: CCF for each species, recomputed in FVS so setting will
                likely have no effect
            spsdi: SDI maximums for each species
            spsiteindx: Species site indices
            bfmind: Min diameter related to BFVOLUME keyword
            bftopd: Top diameter related to BFVOLUME keyword
            bfstmp: Stump height related to BFVOLUME keyword
            frmcls: Form class related to BFVOLUME keyword
            bfmeth: Volume calculation code related to BFVOLUME keyword
                (internal FVS variable methb)
            mcmind: Min diameter related to VOLUME keyword (internal FVS
                variable dbhmin)
            mctopd: Top diameter related to VOLUME keyword (internal FVS
                variable topd)
            mcstmp: Stump height related to VOLUME keyword (internal FVS
                variable stmp)
            mcmeth: Volume calculation code related to VOLUME keyword (internal
                FVS variable methc)
            baimult: Basal area increment multiplier for large trees (internal
                FVS variable xdmult)
            htgmult: Height growth multiplier for large trees (internal FVS
                variable xhmult)
            mortmult: Mortality rate multiplier (internal FVS variable xmmult)
            mortdia1: Lower diameter limit for mortality multiplier (internal
                FVS variable xmdia1)
            mortdia2: Upper diameter limit for mortality multiplier (internal
                FVS variable xmdia2)
            regdmult: Diameter growth mulitplier for regeneration (internal FVS
                variable xrdmlt)
            reghmult: Height growth multiplier for regeneration (internal FVS
                variable xrhmlt)
        """
        return SPECIES.frame(self._invoke, self.dims[STR_MAXSPECIES])

    def get_species_attr(self, attr: str) -> npt.NDArray[np.float64]:
        """Gets a single attribute for all existing species.

        Args:
            attr (str): name of species attribute to fetch

        Returns:
            a new array with the attribute's value for every species

        Raises:
            NameError: If FVS does not recognize `attr`.
        """
        return SPECIES.get(self._invoke, attr, self.dims[STR_MAXSPECIES])

    def set_species_attr(self, attr: str, arr: npt.NDArray[np.float64]) -> None:
        """Sets a single attribute for all existing species.

        Args:
            attr (str): name of species attribute to set
            arr (npt.NDArray[np.float64]): values to set, shape `(maxspecies,)`

        Raises:
            NameError: If FVS does not recognize `attr`.
            ValueError: If `arr` is not shape `(maxspecies,)`.
        """
        SPECIES.set(self._invoke, attr, arr, self.dims[STR_MAXSPECIES])

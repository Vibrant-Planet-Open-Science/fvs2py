"""Species codes and per-species attribute access mixin."""

from __future__ import annotations

import ctypes as ct
import warnings

import numpy as np
import numpy.typing as npt
import pandas as pd  # type: ignore[import-untyped]

from fvs2py.common import fvs_property
from fvs2py.constants import (
    SPECIES_COLUMN_NAMES,
    STR_C_CONTIGUOUS,
    STR_MAXSPECIES,
)
from fvs2py.enums import FvsAttributeAccessor


class SpeciesMixin:
    """Expose species metadata and per-species attribute get/set helpers.

    Assumes the composed class provides the foreign-function attributes
    ``_fvsSpeciesCode`` and ``_fvsSpeciesAttr`` (resolved by
    :class:`fvs2py._core.FvsCore`) and the ``_species_attrs`` mapping
    seeded by ``FVS._initialize_attributes``. Uses ``self.dims`` from
    :class:`StandMixin`.
    """

    _fvsSpeciesCode: ct._FuncPointer
    _fvsSpeciesAttr: ct._FuncPointer
    _species_attrs: dict[str, npt.NDArray[np.float64] | None]
    dims: dict

    @fvs_property
    def species(self) -> pd.DataFrame:
        """Returns species codes and attributes for all species."""
        codes = self.species_codes
        attrs = self.species_attrs
        return codes.merge(attrs, left_index=True, right_index=True, copy=False)

    @fvs_property
    def species_codes(self) -> pd.DataFrame:
        """Fetch the various codes used to refer to different tree species."""
        dims = self.dims

        _fvs_spp = ct.create_string_buffer(4)
        _fia_spp = ct.create_string_buffer(4)
        _plants_spp = ct.create_string_buffer(6)
        returncd = ct.c_int(0)

        spp_codes = pd.DataFrame(
            index=range(dims[STR_MAXSPECIES]),
            columns=SPECIES_COLUMN_NAMES,
        )

        for i in range(dims[STR_MAXSPECIES]):
            self._fvsSpeciesCode(
                _fvs_spp,
                _fia_spp,
                _plants_spp,
                ct.c_int(i + 1),
                ct.c_int(0),
                ct.c_int(0),
                ct.c_int(0),
                ct.c_int(0),
            )
            if returncd.value != 0:
                msg = f"Index {i + 1} out of range"
                raise IndexError(msg)
            spp_codes.iloc[i] = (
                i + 1,
                _fvs_spp.value.decode().strip(),
                _fia_spp.value.decode().strip(),
                _plants_spp.value.decode().strip(),
            )

        return spp_codes

    @fvs_property
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
        for attr in self._species_attrs:
            _ = self.get_species_attr(attr)

        attrs = pd.DataFrame(self._species_attrs, copy=False)
        if (attrs == 0).all().all():
            warnings.warn("No species attributes initialized yet.")
            return attrs.replace(0, None)

        return attrs

    def get_species_attr(self, attr: str) -> npt.NDArray[np.float64]:
        """Gets a single attribute for all existing species.

        Args:
            attr (str): name of species attribute to fetch

        Returns:
            array with values of requested attribute for all trees

        """
        self._species_attr(attr, FvsAttributeAccessor.GET)
        return self._species_attrs[attr]

    def set_species_attr(self, attr: str, arr: npt.NDArray[np.float64]) -> None:
        """Sets a single attribute for all existing species.

        Args:
            attr (str): name of species attribute to fetch
            arr (npt.NDArray[np.float64]): array of values to set

        """
        return self._species_attr(attr, FvsAttributeAccessor.SET, arr)

    def _species_attr(
        self,
        attr: str,
        action: FvsAttributeAccessor,
        arr: npt.NDArray[np.float64] | None = None,
    ) -> None:
        """Gets or sets a single attribute for all existing species.

        Args:
            attr (str): name of species attribute to get or set
            action (FvsAttributeAccessor): 'get' or 'set'
            arr (optional, npt.NDArray[np.float64]): array of values to set
        """
        if attr not in self._species_attrs:
            msg = "Invalid variable requested. Valid options are"
            raise NameError(msg, self._species_attrs)

        dims = self.dims
        if (
            action == FvsAttributeAccessor.GET
            and self._species_attrs[attr] is None
        ):
            self._species_attrs[attr] = np.empty(
                dtype=np.float64, shape=(dims[STR_MAXSPECIES])
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
            self._species_attrs[attr] = arr

        self._fvsSpeciesAttr.argtypes = [
            ct.POINTER(ct.c_char),  # attr name
            ct.POINTER(ct.c_int),  # number of characters in attr name
            ct.POINTER(ct.c_char),  # action (set or get)
            np.ctypeslib.ndpointer(  # type: ignore[arg-type]
                np.float64, shape=(dims[STR_MAXSPECIES]), flags=STR_C_CONTIGUOUS
            ),  # array to fill
            ct.POINTER(ct.c_int),  # return code
        ]
        self._fvsSpeciesAttr.restype = None

        rtncode = ct.c_int(0)
        self._fvsSpeciesAttr(
            ct.c_char_p(attr.encode()),  # attribute requested
            ct.c_int(len(attr)),  # number of characters in attr name
            ct.c_char_p(action.encode()),  # "set" or "get"
            self._species_attrs[attr],  # array to fill
            rtncode,  # return code of setting/getting operation
        )
        ERRS = {
            0: "OK",
            1: "name not found",
            4: "length of name string was too large or small",
        }

        if rtncode.value != 0:
            if rtncode.value == 1:
                msg = f"{attr} not found among species attributes"
                raise NameError(msg)
            raise RuntimeError(ERRS[rtncode.value])

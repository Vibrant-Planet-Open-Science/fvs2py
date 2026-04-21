"""Public :class:`FVS` class, assembled from focused mixins over :class:`FvsCore`."""

from __future__ import annotations

import ctypes as ct
import os

from fvs2py._core import FvsCore
from fvs2py._mixins import (
    ControlMixin,
    EventMixin,
    SimulationMixin,
    SpeciesMixin,
    StandMixin,
    TreesMixin,
)
from fvs2py.common import class_requires_fvs_library
from fvs2py.constants import EVMON_ATTRS, SPECIES_ATTRS, TREE_ATTRS
from fvs2py.enums import FvsSimulationState


@class_requires_fvs_library
class FVS(
    EventMixin,
    TreesMixin,
    SpeciesMixin,
    StandMixin,
    SimulationMixin,
    ControlMixin,
    FvsCore,
):
    """Main class for interacting with FVS at runtime.

    Public behavior is contributed by the six mixins
    (:class:`EventMixin`, :class:`TreesMixin`, :class:`SpeciesMixin`,
    :class:`StandMixin`, :class:`SimulationMixin`, :class:`ControlMixin`);
    this class just initializes the Python-side buffers they rely on and
    wires the library-reload hook.
    """

    def __init__(self, lib_path: str | os.PathLike) -> None:
        """Load the FVS shared library and initialize per-instance buffers.

        Args:
            lib_path: Path to the FVS shared library.
        """
        super().__init__(lib_path=lib_path)
        self._initialize_attributes()

    def _initialize_attributes(self) -> None:
        """Reset all Python-side buffers and state tracked alongside FVS.

        Called both at construction and after :meth:`_reload_fvs` so the
        mixins can rely on a known set of pre-initialized attributes.
        """
        self.keyfile_path = None
        self.keyfile = None
        self._evmon_attrs = dict.fromkeys(EVMON_ATTRS)
        self._exit_code = ct.c_int(0)
        self._itrncd = ct.c_int(-1)
        self._maxcycles = ct.c_int(0)
        self._maxplots = ct.c_int(0)
        self._maxspecies = ct.c_int(0)
        self._maxtrees = ct.c_int(0)
        self._mgmt_id = ct.create_string_buffer(4)
        self._ncycles = ct.c_int(0)
        self._nplots = ct.c_int(0)
        self._ntrees = ct.c_int(0)
        self._restart_code = ct.c_int(0)
        self._species_attrs = dict.fromkeys(SPECIES_ATTRS)
        self._stand_cn = ct.create_string_buffer(40)
        self._stand_id = ct.create_string_buffer(26)
        self._state = FvsSimulationState.IDLE
        self._stop_point_code = None
        self._stop_point_year = None
        self._tree_attrs = TREE_ATTRS
        self._trees = dict.fromkeys(TREE_ATTRS)

    def _reload_fvs(self) -> None:
        """Unload the current library, load a fresh one, and reset buffers."""
        self._unload_fvs()
        self._load_fvs()
        self._initialize_attributes()

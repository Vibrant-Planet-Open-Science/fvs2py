"""Public `FVS` class, assembled from focused mixins over `FvsCore`."""

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
    SVSMixin,
    TreesMixin,
)
from fvs2py.constants import EVMON_ATTRS


class FVS(
    EventMixin,
    SVSMixin,
    TreesMixin,
    SpeciesMixin,
    StandMixin,
    SimulationMixin,
    ControlMixin,
    FvsCore,
):
    """Main class for interacting with FVS at runtime.

    Public behavior is contributed by the seven mixins
    (`EventMixin`, `SVSMixin`, `TreesMixin`,
    `SpeciesMixin`, `StandMixin`, `SimulationMixin`,
    `ControlMixin`); this class just initializes the Python-side
    buffers they rely on and wires the library-reload hook.
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

        Called both at construction and after `_reload_fvs` so the
        mixins can rely on a known set of pre-initialized attributes.
        """
        self.keyfile_path = None
        self.keyfile = None
        self._evmon_attrs = dict.fromkeys(EVMON_ATTRS)
        self._itrncd = ct.c_int(-1)
        self._mgmt_id = ct.create_string_buffer(4)
        self._stand_cn = ct.create_string_buffer(40)
        self._stand_id = ct.create_string_buffer(26)
        self._stop_point_code = None
        self._stop_point_year = None

    def _reload_fvs(self) -> None:
        """Unload the current library, load a fresh one, and reset buffers."""
        self._unload_fvs()
        self._load_fvs()
        self._initialize_attributes()

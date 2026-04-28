"""Focused mixins that compose the :class:`fvs2py.FVS` public API.

Each mixin owns a coherent slice of FVS functionality and assumes the instance
already has ``self._lib`` plus the resolved ``_fvsXyz`` foreign-function
attributes from :class:`fvs2py._core.FvsCore` and the Python-side buffers
initialized by ``FVS._initialize_attributes``.
"""

from fvs2py._mixins.control import ControlMixin
from fvs2py._mixins.events import EventMixin
from fvs2py._mixins.simulation import SimulationMixin
from fvs2py._mixins.species import SpeciesMixin
from fvs2py._mixins.stand import StandMixin
from fvs2py._mixins.svs import SVSMixin
from fvs2py._mixins.trees import TreesMixin

__all__ = [
    "ControlMixin",
    "EventMixin",
    "SVSMixin",
    "SimulationMixin",
    "SpeciesMixin",
    "StandMixin",
    "TreesMixin",
]

"""Declarative ctypes signatures for FVS routines.

Holds a single source of truth mapping FVS routine names (as exposed by the
shared library) to their ctypes ``argtypes``/``restype``. ``FvsCore`` consumes
this during routine resolution and applies the signature to each resolved
foreign function exactly once, eliminating per-call ``argtypes``/``restype``
reassignment at call sites.

Only routines with a static argument shape live here. Routines whose argument
shapes depend on runtime dimensions (``fvsSummary``, ``fvsSpeciesAttr``,
``fvsTreeAttr``) still set ``argtypes`` locally before calling, since the
shapes cannot be decided at import time.

This mapping is being progressively retired in favor of the declarative
:data:`fvs2py._routines.FVS_ROUTINES` registry; entries are removed as each
mixin migrates to :meth:`fvs2py._core.FvsCore._invoke`.
"""

from __future__ import annotations

import ctypes as ct
from collections.abc import Mapping
from types import MappingProxyType
from typing import NamedTuple


class Signature(NamedTuple):
    """Ctypes call signature for a single FVS routine.

    Attributes:
        argtypes: Tuple of ctypes types describing the routine's argument list
            in declaration order.
        restype: Ctypes return type, or ``None`` if the routine returns nothing.
    """

    argtypes: tuple[type, ...]
    restype: type | None = None


FVS_SIGNATURES: Mapping[str, Signature] = MappingProxyType(
    {
        "fvsDimSizes": Signature((ct.POINTER(ct.c_int),) * 7),
        "fvsSetStoppointCodes": Signature((ct.POINTER(ct.c_int),) * 2),
        "fvsSetCmdLine": Signature(
            (ct.c_char_p, ct.POINTER(ct.c_int), ct.POINTER(ct.c_int)),
        ),
        "fvsStandID": Signature(
            (ct.c_char_p,) * 3 + (ct.POINTER(ct.c_int),) * 3,
        ),
        "fvsSpeciesCode": Signature(
            (ct.c_char_p,) * 3 + (ct.POINTER(ct.c_int),) * 5,
        ),
    }
)
"""Immutable registry of static-shape FVS routine signatures."""

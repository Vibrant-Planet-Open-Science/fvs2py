"""Symbolic names for FVS integer status codes and string accessors.

All status-code enums are :class:`IntEnum` subclasses, so their members compare
equal to the corresponding raw integers returned/accepted by FVS. This keeps
call-site ergonomics unchanged (``fvs.itrncd == FvsItrnCode.NOT_STARTED`` works
alongside ``fvs.itrncd == -1``) while giving callers readable constants.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import Self


class FvsVariant(StrEnum):
    """Enumeration of supported FVS Variants."""

    ALASKA = "AK"  # Southeast Alaska and Coastal British Columbia
    BLUE_MOUNTAINS = "BM"  # Blue Mountains
    INLAND_CALIFORNIA = "CA"  # Inland California and Southern Cascades (ICASCA)
    CENTRAL_IDAHO = "CI"  # Central Idaho
    CENTRAL_ROCKIES = "CR"  # Central Rockies
    CENTRAL_STATES = "CS"  # Central States
    EASTERN_CASCADES = "EC"  # East Cascades
    EASTERN_MONTANA = "EM"  # Eastern Montana
    INLAND_EMPIRE = "IE"  # Inland Empire
    KOOTENAI = "KT"  # Kootenai, Kaniksu, and Tally Lake (KooKanTL)
    LAKE_STATES = "LS"  # Lake States
    KLAMATH_MOUNTAINS = "NC"  # Klamath Mountains (and northern California)
    NORTHEAST_US = "NE"  # Northeastern US
    ORGANON_SOUTHWEST = "OC"  # Organon Southwest
    ORGANON_PACIFIC = "OP"  # Organon Pacific Northwest
    PACIFIC_COAST = "PN"  # Pacific Northwest Coast
    SOUTHERN_US = "SN"  # Southern US
    SOUTHERN_OREGON = (
        "SO"  # South Central Oregon and Northeast California (SORNEC)
    )
    TETONS = "TT"  # Tetons
    UTAH = "UT"  # Utah
    WESTERN_CASCADES = "WC"  # Westside Cascades
    WESTERN_SIERRAS = "WS"  # Western Sierra Nevada


class FvsAttributeAccessor(StrEnum):
    """How an FVS attribute is to be accessed."""

    GET = "get"
    SET = "set"


class FvsItrnCode(IntEnum):
    """Return-code values reported by ``fvsGetRtnCode`` / :attr:`FVS.itrncd`."""

    NOT_STARTED = -1
    GOOD_RUNNING_STATE = 0
    ERROR = 1
    FINISHED_ALL_STANDS = 2


class FvsExitCode(IntEnum):
    """Exit-code values reported by ``fvsGetICCode`` / :attr:`FVS.exit_code`."""

    NO_ERROR = 0
    INPUT_DATA_ERROR = 1
    KEYWORD_ERROR = 2
    EXTENSION_OR_GROUP_ACTIVITIES_ERROR = 3
    SCRATCH_FILE_ERROR = 4


class FvsRestartCode(IntEnum):
    """Restart-code values reported by ``fvsGetRestartCode``.

    Indicates where inside a cycle FVS stopped after the most recent call to
    :meth:`FVS.run`.
    """

    INITIALIZED = 0
    BEFORE_FIRST_EVMON = 1
    AFTER_FIRST_EVMON = 2
    BEFORE_SECOND_EVMON = 3
    AFTER_SECOND_EVMON = 4
    AFTER_GROWTH_AND_MORTALITY = 5
    BEFORE_ESTAB = 6
    DONE_RUNNING_STAND = 100


class FvsStopPointCode(IntEnum):
    """Stop-point-code values accepted by ``fvsSetStoppointCodes``.

    Selects where inside a cycle FVS should pause during :meth:`FVS.run`.
    """

    EVERY_STOP_LOCATION = -1
    NEVER_STOP = 0
    BEFORE_FIRST_EVMON = 1
    AFTER_FIRST_EVMON = 2
    BEFORE_SECOND_EVMON = 3
    AFTER_SECOND_EVMON = 4
    AFTER_GROWTH_AND_MORTALITY = 5
    BEFORE_ESTAB = 6
    AFTER_INPUT_BEFORE_IMPUTE = 7


class FvsAttrReturnCode(IntEnum):
    """Return-code values reported by attribute-accessor FVS routines.

    Produced by ``fvsSpeciesAttr``, ``fvsTreeAttr``, and sibling routines with
    the same convention in the trailing ``rtncode`` parameter. Each member
    carries a ``message`` attribute describing the condition, suitable for
    use in an error message. Codes 2 and 3 are only reported by
    ``fvsTreeAttr``; they're documented on the shared enum so a single
    policy can cover every attr accessor.
    """

    message: str

    OK = 0, "OK"
    NAME_NOT_FOUND = 1, "name not found"
    NTREES_EXCEEDS_MAX = 2, "ntrees is greater than the maximum allowed"
    TREE_COUNT_MISMATCH = 3, "there were more or fewer trees than ntrees"
    NAME_LENGTH_INVALID = 4, "length of name string was too large or small"

    def __new__(cls, value: int, message: str) -> Self:
        """Construct a member that carries both the int value and a message.

        Args:
            value: Integer value reported by FVS.
            message: Human-readable description of the return code.

        Returns:
            A new :class:`FvsAttrReturnCode` member with ``message`` attached.
        """
        obj = int.__new__(cls, value)
        obj._value_ = value
        obj.message = message
        return obj


class FvsSimulationState(StrEnum):
    """Python-side state of the FVS simulation lifecycle.

    Tracked on ``FVS._state`` so that :meth:`FVS.run` can guard against
    re-entrant invocation and so callers (or future batch helpers) can reason
    about whether a simulation is idle, in-flight, finished, or has failed.
    These values are opaque identifiers; they do not correspond to any FVS
    return code.
    """

    IDLE = "idle"
    RUNNING = "running"
    COMPLETE = "complete"
    ERROR = "error"

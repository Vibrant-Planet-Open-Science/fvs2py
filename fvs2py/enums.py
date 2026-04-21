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


class FvsBaseActivity(IntEnum):
    """Activity codes for the FVS base model.

    Names match the keywords in the FVS Keyword Guide (no extension prefix,
    since the extension is implicit in this enum's type).
    """

    TREELIST = 80
    CRNMULT = 81
    MANAGED = 82
    FIXCW = 90
    BAIMULT = 91
    HTGMULT = 92
    REGHMULT = 93
    MORTMULT = 94
    REGDMULT = 96
    FIXMORT = 97
    FIXDG = 98
    FIXHTG = 99
    SYSTEM = 100
    HTGSTOP = 110
    TOPKILL = 111
    SETSITE = 120
    ATRTLIST = 198
    CUTLIST = 199
    MINHARV = 200
    SPECPREF = 201
    TCONDMLT = 202
    YARDLOSS = 203
    FVSSTAND = 204
    CRUZFILE = 205
    MCDEFECT = 215
    BFDEFECT = 216
    VOLUME = 217
    BFVOLUME = 218
    THINAUTO = 222
    THINBTA = 223
    THINATA = 224
    THINBBA = 225
    THINABA = 226
    THINPRSC = 227
    THINDBH = 228
    SALVAGE = 229
    THINSDI = 230
    THINCC = 231
    THINHT = 232
    THINMIST = 233
    THINRDEN = 234
    THINPT = 235
    THINRDSL = 236
    SETPTHIN = 248
    PRUNE = 249
    COMPRESS = 250
    FERTILIZ = 260
    RESETAGE = 443


class FvsDatabaseActivity(IntEnum):
    """Activity codes for the FVS database input/output extension."""

    SQLIN = 101
    SQLOUT = 102


class FvsEstablishmentActivity(IntEnum):
    """Activity codes for the FVS Establishment extension."""

    SPECMULT = 95
    TALLY = 427
    TALLYONE = 428
    TALLYTWO = 429
    PLANT = 430
    NATURAL = 431
    ADDTREES = 432
    STOCKADJ = 440
    HTADJ = 442
    SPROUT = 450
    # NATURAL (490) is documented in some FVS variant guides but is
    # omitted from rFVS's activity table and from this enum until we
    # have evidence it is live in the shared library we target.
    BURNPREP = 491
    MECHPREP = 493


class FvsCoverActivity(IntEnum):
    """Activity codes for the FVS Cover extension."""

    COVER = 900


class FvsMistletoeActivity(IntEnum):
    """Activity codes for the FVS Dwarf Mistletoe extension."""

    MISTMULT = 2001
    MISTPREF = 2002
    MISTMORT = 2003
    MISTHMOD = 2004
    MISTGMOD = 2005
    MISTPINF = 2006
    MISTABLE = 2007


class FvsFireAndFuelsActivity(IntEnum):
    """Activity codes for the FVS Fire and Fuels extension."""

    SALVSP = 2501
    SOILHEAT = 2503
    BURNREPT = 2504
    MOISTURE = 2505
    SIMFIRE = 2506
    FLAMEADJ = 2507
    POTFIRE = 2508
    SNAGOUT = 2512
    FUELOUT = 2515
    SALVAGE = 2520
    FUELINIT = 2521
    SNAGINIT = 2522
    PILEBURN = 2523
    FUELTRET = 2525
    FUELREPT = 2527
    MORTREPT = 2528
    DROUGHT = 2529
    FUELMOVE = 2530
    FUELMODL = 2538
    DEFULMOD = 2539
    CARBREPT = 2544
    CARBCUT = 2545
    CANFPROF = 2547
    FUELFOTO = 2548
    FIRECALC = 2549
    FMODLIST = 2550
    DWDVLOUT = 2551
    DWDCVOUT = 2552
    FUELSOFT = 2553


class FvsEconomicsActivity(IntEnum):
    """Activity codes for the FVS Economics extension."""

    PRETEND = 2605
    SEVSTART = 2606
    SPECCST = 2607
    SPECRVN = 2608
    STRTECON = 2609


FvsActivity = (
    FvsBaseActivity
    | FvsDatabaseActivity
    | FvsEstablishmentActivity
    | FvsCoverActivity
    | FvsMistletoeActivity
    | FvsFireAndFuelsActivity
    | FvsEconomicsActivity
)
"""Union of every per-extension FVS activity enum.

Any :class:`IntEnum` member from the extension-scoped activity enums is a
valid :class:`FvsActivity`. Callers pass a member from the appropriate
extension enum (``FvsBaseActivity.SALVAGE`` vs. ``FvsFireAndFuelsActivity.SALVAGE``);
``int(activity)`` unwraps it to the underlying FVS code for the library
call.
"""


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

"""Stateless FVS calls behind `FVS`.

Each function takes `invoke` (`FvsCore._invoke`) and keeps no Python-side state.
Some still change the simulation inside FVS (`add_trees`, `add_activity`,
`set_evmon`).
"""

from __future__ import annotations

import ctypes as ct
import warnings
from collections.abc import Iterable

import numpy as np
import pandas as pd

from fvs2py._attributes import EVMON, TREES, Invoke
from fvs2py.constants import (
    ADD_TREES_COLS,
    MGMT_ID_COLUMN_NAME,
    SPECIES_COLUMN_NAMES,
    STAND_CN_COLUMN_NAME,
    STAND_ID_COLUMN_NAME,
    STR_MAXSPECIES,
    STR_MAXTREES,
    STR_NCWDOBJS,
    STR_NCYCLES,
    STR_NDEADOBJS,
    STR_NPLOTS,
    STR_NSVSOBJS,
    STR_NTREES,
    SUMMARY_COLS,
    SVS_CWD_OBJ_ATTRS,
    SVS_LIVE_OBJ_ATTRS,
    SVS_SNAG_OBJ_ATTRS,
)
from fvs2py.enums import FvsActivity


def _read_text(invoke: Invoke, name: str, size: int) -> str:
    """Call a routine that fills a `size`-byte text buffer and decode it."""
    buf = ct.create_string_buffer(size)
    nch = invoke(name, buf=buf, buflen=ct.c_int(size))
    return buf.raw[:nch].decode()


def version(invoke: Invoke) -> str:
    """Short FVS version string, `"<tag> (<org>)"`."""
    return _read_text(invoke, "fvsGetVersion", 64)


def build_info(invoke: Invoke) -> dict[str, str]:
    """FVS build provenance, keyed by field name."""
    text = _read_text(invoke, "fvsGetBuildInfo", 512)
    fields = (line.partition(":") for line in text.splitlines())
    return {k.strip(): v.strip() for k, _, v in fields}


def stand_ids(invoke: Invoke) -> dict[str, str]:
    """Stand ID, stand CN, and management ID of the current stand."""
    stand_id = ct.create_string_buffer(26)
    stand_cn = ct.create_string_buffer(40)
    mgmt_id = ct.create_string_buffer(4)
    invoke(
        "fvsStandID",
        stand_id=stand_id,
        stand_cn=stand_cn,
        mgmt_id=mgmt_id,
        stand_id_len=ct.c_int(0),
        stand_cn_len=ct.c_int(0),
        mgmt_id_len=ct.c_int(0),
    )
    return {
        STAND_ID_COLUMN_NAME: stand_id.value.decode().strip(),
        STAND_CN_COLUMN_NAME: stand_cn.value.decode().strip(),
        MGMT_ID_COLUMN_NAME: mgmt_id.value.decode().strip(),
    }


def summary(invoke: Invoke) -> pd.DataFrame | None:
    """Summary statistics for every cycle FVS has started, or `None`."""
    ncycles = invoke("fvsDimSizes")[STR_NCYCLES]
    if ncycles == 0:
        return None
    rows = np.zeros(dtype=np.intc, shape=(ncycles + 1, len(SUMMARY_COLS)))
    for i in range(ncycles + 1):
        invoke(
            "fvsSummary",
            summary=rows[i],
            icycle=ct.c_int(i + 1),
            ncycles=ct.c_int(ncycles),
            maxrow=ct.c_int(0),
            maxcol=ct.c_int(0),
        )
    started = ~(rows == 0).all(axis=1)
    return pd.DataFrame(rows[started, :], columns=SUMMARY_COLS)


def species_codes(invoke: Invoke) -> pd.DataFrame:
    """FVS index, FVS alpha, FIA, and PLANTS codes for every species slot."""
    fvs_spp = ct.create_string_buffer(4)
    fia_spp = ct.create_string_buffer(4)
    plants_spp = ct.create_string_buffer(6)
    maxspecies = invoke("fvsDimSizes")[STR_MAXSPECIES]
    codes = pd.DataFrame(index=range(maxspecies), columns=SPECIES_COLUMN_NAMES)
    for i in range(maxspecies):
        invoke(
            "fvsSpeciesCode",
            fvs_spp=fvs_spp,
            fia_spp=fia_spp,
            plants_spp=plants_spp,
            index=ct.c_int(i + 1),
            fvs_spp_len=ct.c_int(0),
            fia_spp_len=ct.c_int(0),
            plants_spp_len=ct.c_int(0),
        )
        codes.iloc[i] = (
            i + 1,
            fvs_spp.value.decode().strip(),
            fia_spp.value.decode().strip(),
            plants_spp.value.decode().strip(),
        )
    return codes


def ntrees(invoke: Invoke) -> int:
    """Current tree count, warning when there are none yet."""
    n = invoke("fvsDimSizes")[STR_NTREES]
    if n == 0:
        warnings.warn("No trees in FVS yet.")
    return n


def trees(invoke: Invoke) -> pd.DataFrame | None:
    """Every tree attribute as a column, or `None` if there are no trees."""
    n = ntrees(invoke)
    return TREES.frame(invoke, n) if n else None


def add_trees(invoke: Invoke, tree_df: pd.DataFrame) -> None:
    """Validate `tree_df` and append its rows to the current stand."""
    missing = [c for c in ADD_TREES_COLS if c not in tree_df.columns]
    if missing:
        msg = (
            f"tree_df is missing required column(s) {missing}; "
            f"expected all of {list(ADD_TREES_COLS)}"
        )
        raise ValueError(msg)

    n = len(tree_df)
    new = tree_df[list(ADD_TREES_COLS)].astype(np.float64)
    if new.isna().any().any():
        msg = "No null values allowed in trees to add."
        raise ValueError(msg)

    d = invoke("fvsDimSizes")
    if d[STR_MAXTREES] < d[STR_NTREES] + n:
        room = d[STR_MAXTREES] - d[STR_NTREES]
        msg = f"Only room for {room} new trees but {n} supplied."
        raise ValueError(msg)

    if d[STR_NPLOTS] == 0:
        msg = "No inventory plots loaded yet."
        raise RuntimeError(msg)

    if not new["plot"].isin(range(1, d[STR_NPLOTS] + 1)).all():
        msg = "Plot codes must be within range already defined."
        raise ValueError(msg)

    if not new["species"].isin(species_codes(invoke)["fvs_index"]).all():
        msg = "Unrecognized species code(s). Use FVS Species Index."
        raise ValueError(msg)

    invoke(
        "fvsAddTrees",
        **{c: new[c].to_numpy() for c in ADD_TREES_COLS},
        ntrees=ct.c_int(n),
    )


def get_evmon(invoke: Invoke, attr: str) -> float | None:
    """Current value of one Event Monitor variable, or `None` before cycle 1."""
    if invoke("fvsDimSizes")[STR_NCYCLES] == 0:
        return None
    return float(EVMON.get(invoke, attr, 1)[0])


def set_evmon(invoke: Invoke, attr: str, val: float) -> None:
    """Set one Event Monitor variable; a no-op before cycle 1."""
    if invoke("fvsDimSizes")[STR_NCYCLES] == 0:
        return
    EVMON.set(invoke, attr, np.array([val], dtype=np.float64), 1)


def add_activity(
    invoke: Invoke,
    year: int,
    activity: FvsActivity | int,
    params: Iterable[float] | None,
) -> None:
    """Schedule `activity` in `year` with `params`."""
    if invoke("fvsDimSizes")[STR_NCYCLES] == 0:
        msg = (
            "No inventory plots loaded yet. Consider FVS.run(7, 0) to "
            "load inventory data and run configuration before "
            "simulating anything else."
        )
        raise RuntimeError(msg)

    arr = np.array(list(() if params is None else params), dtype=np.float64)
    if np.isnan(arr).any():
        msg = "params may not contain NaN values."
        raise ValueError(msg)

    invoke(
        "fvsAddActivity",
        year=ct.c_int(int(year)),
        activity_code=ct.c_int(int(activity)),
        params=arr,
        nparams=ct.c_int(len(arr)),
    )


def svs_count(invoke: Invoke, attr: str) -> int:
    """Current object count for the SVS object kind `attr` belongs to."""
    if attr in SVS_LIVE_OBJ_ATTRS:
        key = STR_NSVSOBJS
    elif attr in SVS_SNAG_OBJ_ATTRS:
        key = STR_NDEADOBJS
    elif attr in SVS_CWD_OBJ_ATTRS:
        key = STR_NCWDOBJS
    else:
        msg = f"unrecognized SVS object attribute: {attr!r}"
        raise NameError(msg)
    return invoke("fvsSVSDimSizes")[key]

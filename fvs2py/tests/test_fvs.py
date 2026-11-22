"""Unit tests for the public `FVS` API against a fake FVS library.

`FakeLib` supplies plain Python functions in place of the library's routines, so
every call still goes through `FvsCore._invoke` and the routine registry.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fvs2py import FVS, _core
from fvs2py._attributes import FFE, SPECIES, SVS_OBJECTS, TREES
from fvs2py.constants import (
    FFE_FALLYRS_ATTRS,
    MGMT_ID_COLUMN_NAME,
    STAND_CN_COLUMN_NAME,
    STAND_ID_COLUMN_NAME,
    STR_MAXCYCLES,
    STR_MAXPLOTS,
    STR_MAXSPECIES,
    STR_MAXTREES,
    STR_MXCWDOBJS,
    STR_MXDEADOBJS,
    STR_MXSVSOBJS,
    STR_NCWDOBJS,
    STR_NCYCLES,
    STR_NDEADOBJS,
    STR_NPLOTS,
    STR_NSVSOBJS,
    STR_NTREES,
)
from fvs2py.enums import (
    FvsBaseActivity,
    FvsExitCode,
    FvsItrnCode,
    FvsRestartCode,
    FvsStopPointCode,
)

KEYFILE = "STDIDENT\n"

# One in-memory output table: (name, declared type) columns, then rows. NULL is
# None. The long text overflows the first text buffer, forcing the retry.
LONG = "x" * 200
TABLE_COLS = [
    ("CaseID", "TEXT"),
    ("Year", "INTEGER"),
    ("BA", "REAL"),
    ("StandID", "CHAR(26)"),
]
TABLE_ROWS = [("c1", 2000, 10.5, "S1"), ("c1", 2010, None, LONG)]


class FakeLib:
    """In-memory FVS: fixed dims and codes, stored attribute values."""

    def __init__(self, **overrides):
        self.dims = {
            STR_NTREES: 0,
            STR_NCYCLES: 1,
            STR_NPLOTS: 1,
            STR_MAXTREES: 10,
            STR_MAXSPECIES: 3,
            STR_MAXPLOTS: 1,
            STR_MAXCYCLES: 40,
        }
        self.svs_dims = {
            STR_NSVSOBJS: 2,
            STR_NDEADOBJS: 1,
            STR_NCWDOBJS: 1,
            STR_MXSVSOBJS: 100,
            STR_MXDEADOBJS: 100,
            STR_MXCWDOBJS: 100,
        }
        self.itrncd = int(FvsItrnCode.GOOD_RUNNING_STATE)
        self.restart_code = int(FvsRestartCode.INITIALIZED)
        self.exit_code = 0
        self.add_activity_rc = 0
        self.evmon: dict[str, float] = {}
        self.tables = {"FVS_Summary2": (TABLE_COLS, TABLE_ROWS)}
        self.memory_on = 0
        self.text_always_too_small = False
        for key, value in overrides.items():
            if key in self.dims:
                self.dims[key] = value
            else:
                setattr(self, key, value)
        self.stored: dict[tuple[str, str], np.ndarray] = {}
        self.fvs_calls = 0
        self.activity_calls: list[dict] = []

    def funcs(self):
        lib = self

        def writer(values):
            def write(*outs):
                for out, value in zip(outs, values(), strict=True):
                    out.value = value

            return write

        def table_attr(table):
            def attr(attr_name, _nch, action, *rest):
                *_, arr, rtncode = rest
                name = attr_name.decode()
                if name not in table.names:
                    rtncode.value = 1
                    return
                key = (table.routine, name)
                if action == b"get":
                    arr[:] = lib.stored.get(key, np.zeros(len(arr)))
                else:
                    lib.stored[key] = np.array(arr)
                rtncode.value = 0

            return attr

        def evmon(attr_name, _nch, action, arr, rtncode):
            name = attr_name.decode()
            if action == b"set":
                lib.evmon[name] = float(arr[0])
            elif name in lib.evmon:
                arr[0] = lib.evmon[name]
            else:
                rtncode.value = 1
                return
            rtncode.value = 0

        def fvs(_itrncd):
            lib.fvs_calls += 1

        def stand_id(stand_id, stand_cn, mgmt_id, *_lengths):
            stand_id.value, stand_cn.value, mgmt_id.value = (
                b"S1",
                b"cn-42",
                b"M1",
            )

        def species_code(fvs_spp, fia_spp, plants_spp, _index, *rest):
            fvs_spp.value, fia_spp.value = b"DF", b"202"
            plants_spp.value = b"PSME"
            rest[-1].value = 0

        def add_activity(year, code, params, nparams, rtncode):
            lib.activity_calls.append({
                "year": year.value,
                "code": code.value,
                "params": np.array(params),
                "nparams": nparams.value,
            })
            rtncode.value = lib.add_activity_rc

        def set_stop_points(*_codes):
            pass

        def build_info(buf, _buflen, nch):
            buf.value = (
                b"Version: 2027.1.1\nOrg:     USDAForestService\n"
                b"Remote:  https://github.com/x/fvs.git\nBranch:  main\n"
                b"Commit:  abc1234\nDate:    2026-11-21 19:05:11 +0000"
            )
            nch.value = len(buf.value)

        def put(buf, nch, entries):
            """Write NUL-terminated entries if they fit; return rtncode."""
            data = b"".join(e.encode() + b"\0" for e in entries)
            fits = len(data) <= nch.value
            if fits:
                buf[: len(data)] = data
            nch.value = len(data)
            return 0 if fits else 2

        def lookup(name, rtncode):
            key = name.decode()
            rtncode.value = 4 if not key else 0 if key in lib.tables else 1
            return lib.tables.get(key)

        def text_cols(cols):
            return [
                i for i, (_, t) in enumerate(cols) if "CHAR" in t or t == "TEXT"
            ]

        def set_memory_tables(on, rtncode):
            lib.memory_on = on.value
            rtncode.value = 0

        def table_list(names, nch, ntables, rtncode):
            ntables.value = len(lib.tables)
            rtncode.value = put(names, nch, lib.tables)

        def table_dims(name, _nch, nrow, nnum, ntxt, rtncode):
            if (t := lookup(name, rtncode)) is None:
                return
            cols, rows = t
            nrow.value, ntxt.value = len(rows), len(text_cols(cols))
            nnum.value = len(cols) - ntxt.value

        def table_columns(name, _nch, ncol, *rest):
            cols_buf, ncolch, types, ntypch, istxt, rtncode = rest
            if (t := lookup(name, rtncode)) is None:
                return
            cols, _ = t
            if ncol.value != len(cols):
                ncol.value, rtncode.value = len(cols), 2
                return
            istxt[:] = [i in text_cols(cols) for i in range(len(cols))]
            rtncode.value = max(
                put(cols_buf, ncolch, [c for c, _ in cols]),
                put(types, ntypch, [ty for _, ty in cols]),
            )

        def table_num(name, _nch, _row0, _nrows, _nnum, values, rtncode):
            if (t := lookup(name, rtncode)) is None:
                return
            cols, rows = t
            num = [i for i in range(len(cols)) if i not in text_cols(cols)]
            for r, row in enumerate(rows):
                values[r] = [np.nan if row[i] is None else row[i] for i in num]

        def table_txt(name, _nch, _row0, _nrows, _ntxt, text, ntextch, rtncode):
            if (t := lookup(name, rtncode)) is None:
                return
            cols, rows = t
            txt = text_cols(cols)
            entries = [row[i] or "" for row in rows for i in txt]
            rtncode.value = put(text, ntextch, entries)
            if lib.text_always_too_small:
                rtncode.value = 2

        def clear_table(name, _nch, rtncode):
            if lookup(name, rtncode) is not None:
                del lib.tables[name.decode()]

        return {
            "fvs": fvs,
            "fvsDimSizes": writer(lambda: [*map(lib.dims.get, lib.dims)]),
            "fvsSVSDimSizes": writer(
                lambda: [*map(lib.svs_dims.get, lib.svs_dims)]
            ),
            "fvsGetRtnCode": writer(lambda: [lib.itrncd]),
            "fvsGetRestartCode": writer(lambda: [lib.restart_code]),
            "fvsGetICCode": writer(lambda: [lib.exit_code]),
            "fvsStandID": stand_id,
            "fvsSpeciesCode": species_code,
            "fvsSetStoppointCodes": set_stop_points,
            "fvsGetBuildInfo": build_info,
            "fvsSetMemoryTables": set_memory_tables,
            "fvsTableList": table_list,
            "fvsTableDims": table_dims,
            "fvsTableColumns": table_columns,
            "fvsTableNum": table_num,
            "fvsTableTxt": table_txt,
            "fvsClearTable": clear_table,
            "fvsAddActivity": add_activity,
            "fvsEvmonAttr": evmon,
            "fvsTreeAttr": table_attr(TREES),
            "fvsSpeciesAttr": table_attr(SPECIES),
            "fvsFFEAttrs": table_attr(FFE),
            "fvsSVSObjData": table_attr(SVS_OBJECTS),
        }


@pytest.fixture
def make_fvs(mock_valid_fvs_dll):  # noqa: ARG001 (patches ctypes.CDLL)
    def make(*, keyfile=KEYFILE, started=True, **overrides):
        if started:
            overrides.setdefault("itrncd", int(FvsItrnCode.FINISHED_ALL_STANDS))
        lib = FakeLib(**overrides)
        # Fakes have no real library to evict; drop any earlier one's slot.
        _core._ACTIVE = None
        fvs = FVS(lib_path="/not/a/real/dir/FVSxx.so")
        fvs._funcs.update(lib.funcs())
        fvs.keyfile = keyfile
        return fvs, lib

    return make


def test_build_info_parses_fields(make_fvs):
    fvs, _ = make_fvs()
    assert fvs.build_info == {
        "Version": "2027.1.1",
        "Org": "USDAForestService",
        "Remote": "https://github.com/x/fvs.git",
        "Branch": "main",
        "Commit": "abc1234",
        "Date": "2026-11-21 19:05:11 +0000",
    }


# ---------------------------------------------------------------------------
# Stand
# ---------------------------------------------------------------------------


def test_dims_returns_named_dict(make_fvs):
    fvs, lib = make_fvs()
    assert fvs.dims == lib.dims


def test_stand_ids_without_keyfile_raises(make_fvs):
    fvs, _ = make_fvs(keyfile=None, started=False)
    with pytest.raises(RuntimeError, match="No keyfile loaded yet."):
        fvs.stand_ids


def test_stand_ids_without_run_raises(make_fvs):
    fvs, _ = make_fvs(started=False)
    with pytest.raises(RuntimeError, match="Simulation has not started yet."):
        fvs.stand_ids


def test_setting_stop_points_does_not_start_the_simulation(make_fvs):
    fvs, _ = make_fvs(started=False)
    fvs.set_stop_point_codes(0, 0)
    with pytest.raises(RuntimeError, match="Simulation has not started yet."):
        fvs.stand_ids


def test_stand_ids_returns_decoded_values(make_fvs):
    fvs, _ = make_fvs()
    assert fvs.stand_ids == {
        STAND_ID_COLUMN_NAME: "S1",
        STAND_CN_COLUMN_NAME: "cn-42",
        MGMT_ID_COLUMN_NAME: "M1",
    }


def test_summary_is_none_before_any_cycle(make_fvs):
    fvs, _ = make_fvs(**{STR_NCYCLES: 0})
    assert fvs.summary is None


# ---------------------------------------------------------------------------
# Run lifecycle
# ---------------------------------------------------------------------------


def test_status_codes_are_enum_members(make_fvs):
    fvs, _ = make_fvs(itrncd=2, exit_code=10, restart_code=7)
    assert fvs.itrncd is FvsItrnCode.FINISHED_ALL_STANDS
    assert fvs.exit_code is FvsExitCode.ESTABLISHMENT_OR_COVER_WARNING
    assert fvs.restart_code is FvsRestartCode.AFTER_INPUT_BEFORE_IMPUTE


@pytest.mark.parametrize("code", ["itrncd", "exit_code", "restart_code"])
def test_unknown_status_code_raises(make_fvs, code):
    fvs, _ = make_fvs(**{code: 99})
    with pytest.raises(ValueError, match="99"):
        getattr(fvs, code)


@pytest.mark.parametrize("method", ["run", "run_batch"])
def test_run_without_keyfile_raises(make_fvs, method):
    fvs, _ = make_fvs(keyfile=None, started=False)
    with pytest.raises(RuntimeError, match="No keyfile loaded yet."):
        getattr(fvs, method)()


def test_run_does_not_flush_when_stand_not_done(make_fvs):
    fvs, lib = make_fvs(itrncd=int(FvsItrnCode.FINISHED_ALL_STANDS))
    fvs.run()
    assert lib.fvs_calls == 0


def test_run_flushes_when_stand_done(make_fvs):
    fvs, lib = make_fvs(
        itrncd=int(FvsItrnCode.FINISHED_ALL_STANDS),
        restart_code=int(FvsRestartCode.DONE_RUNNING_STAND),
    )
    fvs.run()
    assert lib.fvs_calls == 1


def test_run_batch_does_not_flush_when_stand_done(make_fvs):
    fvs, lib = make_fvs(
        itrncd=int(FvsItrnCode.FINISHED_ALL_STANDS),
        restart_code=int(FvsRestartCode.DONE_RUNNING_STAND),
    )
    fvs.run_batch()
    assert lib.fvs_calls == 0


def test_run_batch_stops_when_restart_code_leaves_initialized(make_fvs):
    fvs, lib = make_fvs(
        started=False, restart_code=int(FvsRestartCode.BEFORE_FIRST_EVMON)
    )
    fvs.run_batch()
    assert lib.fvs_calls == 1


# ---------------------------------------------------------------------------
# Stop points
# ---------------------------------------------------------------------------


def test_stop_points_are_none_before_they_are_set(make_fvs):
    fvs, _ = make_fvs(started=False)
    assert fvs.stop_point_code is None
    assert fvs.stop_point_year is None


def test_set_stop_point_codes_stores_both(make_fvs):
    fvs, _ = make_fvs(started=False)
    fvs.set_stop_point_codes(3, 2025)
    assert (fvs.stop_point_code, fvs.stop_point_year) == (3, 2025)
    assert fvs.stop_point_code is FvsStopPointCode.BEFORE_SECOND_EVMON


@pytest.mark.parametrize("invalid", [-2, 8, 10, -5])
def test_set_stop_point_codes_rejects_out_of_range(make_fvs, invalid):
    fvs, _ = make_fvs(started=False)
    with pytest.raises(ValueError, match="Invalid value for stop_point_code"):
        fvs.set_stop_point_codes(invalid, 0)


def test_set_stop_point_codes_rejects_year_without_code(make_fvs):
    fvs, _ = make_fvs(started=False)
    with pytest.raises(ValueError, match="Must specify stop_point_year"):
        fvs.set_stop_point_codes(None, 2025)


def test_stop_point_setters_default_the_other_value_to_zero(make_fvs):
    fvs, _ = make_fvs(started=False)
    fvs.stop_point_code = 3
    assert (fvs.stop_point_code, fvs.stop_point_year) == (3, 0)
    fvs, _ = make_fvs(started=False)
    fvs.stop_point_year = 2025
    assert (fvs.stop_point_code, fvs.stop_point_year) == (0, 2025)


def test_stop_point_setters_preserve_the_other_value(make_fvs):
    fvs, _ = make_fvs(started=False)
    fvs.set_stop_point_codes(1, 2020)
    fvs.stop_point_code = 4
    assert (fvs.stop_point_code, fvs.stop_point_year) == (4, 2020)
    fvs.stop_point_year = 2030
    assert (fvs.stop_point_code, fvs.stop_point_year) == (4, 2030)


def test_stop_point_code_setter_validates(make_fvs):
    fvs, _ = make_fvs(started=False)
    with pytest.raises(ValueError, match="Invalid value for stop_point_code"):
        fvs.stop_point_code = 99


# ---------------------------------------------------------------------------
# SVS and FFE
# ---------------------------------------------------------------------------


def test_svs_dim_sizes_returns_named_dict(make_fvs):
    fvs, lib = make_fvs()
    assert fvs.svs_dim_sizes == lib.svs_dims


def test_svs_obj_attr_unknown_name_raises_nameerror(make_fvs):
    fvs, _ = make_fvs()
    with pytest.raises(NameError, match="unrecognized SVS object attribute"):
        fvs.get_svs_obj_attr("nope")


def test_svs_obj_attr_length_follows_object_kind(make_fvs):
    fvs, _ = make_fvs()
    fvs.set_svs_obj_attr("xloc", np.array([3.0, 4.0]))
    assert fvs.get_svs_obj_attr("xloc").tolist() == [3.0, 4.0]
    with pytest.raises(ValueError, match=r"shape \(2,\)"):
        fvs.set_svs_obj_attr("xloc", np.zeros(5))


@pytest.mark.parametrize("attr", FFE_FALLYRS_ATTRS)
def test_ffe_attr_round_trips(make_fvs, attr):
    fvs, _ = make_fvs()
    fvs.set_ffe_attr(attr, np.array([1.5, 2.5, 3.5]))
    assert fvs.get_ffe_attr(attr).tolist() == [1.5, 2.5, 3.5]


def test_ffe_attrs_warns_when_all_zero(make_fvs):
    fvs, _ = make_fvs()
    with pytest.warns(UserWarning, match="No FFE fallyrs attributes"):
        result = fvs.ffe_attrs
    assert result.shape == (3, len(FFE_FALLYRS_ATTRS))
    assert result.isna().all().all()


# ---------------------------------------------------------------------------
# Trees
# ---------------------------------------------------------------------------


def _tree_df(**overrides):
    row = {
        "dbh": 1.0,
        "species": 1.0,
        "ht": 1.0,
        "cratio": 1.0,
        "plot": 1.0,
        "tpa": 1.0,
    }
    return pd.DataFrame([row | overrides])


def test_set_tree_attr_with_wrong_shape_raises_valueerror(make_fvs):
    fvs, _ = make_fvs(**{STR_NTREES: 3})
    with pytest.raises(ValueError, match=r"shape \(3,\)"):
        fvs.set_tree_attr("dbh", np.zeros(5))


def test_trees_warns_and_returns_none_when_empty(make_fvs):
    fvs, _ = make_fvs()
    with pytest.warns(UserWarning, match="No trees in FVS yet."):
        assert fvs.trees is None


def test_add_trees_rejects_missing_columns(make_fvs):
    fvs, _ = make_fvs()
    with pytest.raises(
        ValueError, match=r"missing required column\(s\) \['tpa'\]"
    ):
        fvs.add_trees(_tree_df().drop(columns="tpa"))


def test_add_trees_rejects_null_values(make_fvs):
    fvs, _ = make_fvs()
    with pytest.raises(ValueError, match="No null values allowed"):
        fvs.add_trees(_tree_df(dbh=None))


def test_add_trees_rejects_when_no_plots_loaded(make_fvs):
    fvs, _ = make_fvs(**{STR_NPLOTS: 0})
    with pytest.raises(RuntimeError, match="No inventory plots loaded yet."):
        fvs.add_trees(_tree_df())


def test_add_trees_rejects_unknown_species(make_fvs):
    fvs, _ = make_fvs()
    with pytest.raises(ValueError, match="Unrecognized species code"):
        fvs.add_trees(_tree_df(species=9.0))


# ---------------------------------------------------------------------------
# Event Monitor and activities
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("setup", "match"),
    [
        ({"keyfile": None, "started": False}, "No keyfile loaded yet."),
        ({"started": False}, "Simulation has not started yet"),
    ],
)
def test_evmon_and_activity_preconditions(make_fvs, setup, match):
    fvs, _ = make_fvs(**setup)
    with pytest.raises(RuntimeError, match=match):
        fvs.get_evmon_attr("year")
    with pytest.raises(RuntimeError, match=match):
        fvs.add_activity(2025, FvsBaseActivity.THINPRSC)


def test_get_evmon_attr_is_none_before_any_cycle(make_fvs):
    fvs, _ = make_fvs(**{STR_NCYCLES: 0}, evmon={"year": 2025.0})
    assert fvs.get_evmon_attr("year") is None


def test_get_evmon_attr_returns_float(make_fvs):
    fvs, _ = make_fvs(evmon={"year": 2025.0})
    assert fvs.get_evmon_attr("year") == pytest.approx(2025.0)


def test_get_evmon_attr_unknown_name_raises_nameerror(make_fvs):
    fvs, _ = make_fvs()
    with pytest.raises(NameError, match="name not found"):
        fvs.get_evmon_attr("bogus")


def test_set_evmon_attr_adds_new_name_to_evmon_attrs(make_fvs):
    fvs, _ = make_fvs()
    assert "my_compute_var" not in fvs.evmon_attrs
    fvs.set_evmon_attr("my_compute_var", 3.14)
    assert fvs.evmon_attrs["my_compute_var"] == pytest.approx(3.14)


def test_evmon_attrs_tolerates_name_not_found(make_fvs):
    fvs, _ = make_fvs(evmon={"year": 2025.0})
    result = fvs.evmon_attrs
    assert result["year"] == pytest.approx(2025.0)
    assert result["fire"] is None


def test_add_activity_without_inventory_raises(make_fvs):
    fvs, _ = make_fvs(**{STR_NCYCLES: 0})
    with pytest.raises(RuntimeError, match="No inventory plots loaded yet"):
        fvs.add_activity(2025, FvsBaseActivity.THINPRSC)


def test_add_activity_rejects_nan_params(make_fvs):
    fvs, _ = make_fvs()
    with pytest.raises(ValueError, match="may not contain NaN"):
        fvs.add_activity(2025, FvsBaseActivity.THINPRSC, params=[1.0, np.nan])


def test_add_activity_passes_code_and_params(make_fvs):
    fvs, lib = make_fvs()
    fvs.add_activity(2025, FvsBaseActivity.THINPRSC, params=[1.0, -1.0])
    (call,) = lib.activity_calls
    assert call["year"] == 2025
    assert call["code"] == int(FvsBaseActivity.THINPRSC)
    assert call["params"].tolist() == [1.0, -1.0]
    assert call["nparams"] == 2


@pytest.mark.parametrize("params", [None, [], np.array([])])
def test_add_activity_without_params_sends_empty_buffer(make_fvs, params):
    fvs, lib = make_fvs()
    fvs.add_activity(2025, FvsBaseActivity.TREELIST, params=params)
    assert lib.activity_calls[0]["nparams"] == 0


def test_add_activity_rc_one_raises_valueerror(make_fvs):
    fvs, _ = make_fvs(add_activity_rc=1)
    with pytest.raises(ValueError, match="failed to add the activity"):
        fvs.add_activity(2025, FvsBaseActivity.THINPRSC)


# ---------------------------------------------------------------------------
# Output tables
# ---------------------------------------------------------------------------


def test_load_keyfile_applies_memory_tables(make_fvs, tmp_path):
    fvs, lib = make_fvs(started=False, itrncd=int(FvsItrnCode.NOT_STARTED))
    keyfile = tmp_path / "x.key"
    keyfile.write_text("STDIDENT\nPROCESS\nSTOP\n")
    fvs.memory_tables = True
    fvs.load_keyfile(keyfile)
    assert lib.memory_on == 1


def test_get_table_restores_table_order_and_types(make_fvs):
    fvs, _ = make_fvs()
    df = fvs.get_table("FVS_Summary2")
    assert list(df.columns) == ["CaseID", "Year", "BA", "StandID"]
    assert str(df["Year"].dtype) == "Int64"
    assert df["BA"].dtype == np.float64
    assert df["CaseID"].tolist() == ["c1", "c1"]
    assert df["Year"].tolist() == [2000, 2010]
    assert df["BA"].iloc[0] == 10.5
    assert np.isnan(df["BA"].iloc[1])
    assert df["StandID"].tolist() == ["S1", LONG]


def test_get_table_empty_table_keeps_columns(make_fvs):
    fvs, lib = make_fvs()
    lib.tables["FVS_Summary2"] = (TABLE_COLS, [])
    df = fvs.get_table("FVS_Summary2")
    assert list(df.columns) == ["CaseID", "Year", "BA", "StandID"]
    assert df.empty


def test_get_table_buffer_still_too_small_raises(make_fvs):
    fvs, _ = make_fvs(text_always_too_small=True)
    with pytest.raises(RuntimeError, match="return code: 2"):
        fvs.get_table("FVS_Summary2")


@pytest.mark.parametrize(
    ("name", "exc"), [("Nope", KeyError), ("", ValueError)]
)
def test_get_table_bad_name_raises(make_fvs, name, exc):
    fvs, _ = make_fvs()
    with pytest.raises(exc):
        fvs.get_table(name)


def test_clear_table_removes_it_from_table_names(make_fvs):
    fvs, _ = make_fvs()
    assert fvs.table_names == ["FVS_Summary2"]
    fvs.clear_table("FVS_Summary2")
    assert fvs.table_names == []

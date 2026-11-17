"""Tests for `fvs2py._attributes.AttributeTable` against an in-memory fake FVS."""

from __future__ import annotations

import numpy as np
import pytest

from fvs2py._attributes import EVMON, FFE, SPECIES, SVS_OBJECTS, TREES
from fvs2py._routines import FVS_ROUTINES

TABLES = [TREES, SPECIES, FFE, SVS_OBJECTS, EVMON]
N = 3


class _FakeFvs:
    """Stores attribute values per routine; unknown names report rtncode 1."""

    def __init__(self, table):
        values: dict[str, np.ndarray] = {}

        def routine(attr_name, _nch, action, *rest):
            *_, arr, rtncode = rest
            name = attr_name.decode()
            if name not in table.names:
                rtncode.value = 1
                return
            if action == b"get":
                arr[:] = values.get(name, np.zeros(len(arr)))
            else:
                values[name] = np.array(arr)
            rtncode.value = 0

        self._routine = routine

    def invoke(self, name, /, **kwargs):
        return FVS_ROUTINES[name].call(self._routine, **kwargs)


def _n(table):
    return 1 if table is EVMON else N


@pytest.mark.parametrize("table", TABLES, ids=lambda t: t.routine)
def test_set_then_get_round_trips(table):
    fake = _FakeFvs(table)
    attr, n = table.names[0], _n(table)
    table.set(fake.invoke, attr, np.arange(n, dtype=np.float64) + 1, n)
    assert table.get(fake.invoke, attr, n).tolist() == list(range(1, n + 1))


@pytest.mark.parametrize("table", TABLES, ids=lambda t: t.routine)
def test_get_returns_independent_arrays(table):
    fake = _FakeFvs(table)
    attr, n = table.names[0], _n(table)
    first = table.get(fake.invoke, attr, n)
    first[:] = 99.0
    assert table.get(fake.invoke, attr, n).tolist() == [0.0] * n


@pytest.mark.parametrize("table", TABLES, ids=lambda t: t.routine)
def test_set_rejects_wrong_shape(table):
    fake = _FakeFvs(table)
    n = _n(table)
    with pytest.raises(ValueError, match=rf"shape \({n},\)"):
        table.set(fake.invoke, table.names[0], np.zeros(n + 1), n)


@pytest.mark.parametrize("table", TABLES, ids=lambda t: t.routine)
def test_unknown_name_raises_nameerror(table):
    fake = _FakeFvs(table)
    with pytest.raises(NameError, match="name not found"):
        table.get(fake.invoke, "bogus", _n(table))


@pytest.mark.parametrize("table", [SPECIES, FFE], ids=lambda t: t.routine)
def test_frame_warns_and_blanks_when_all_zero(table):
    fake = _FakeFvs(table)
    with pytest.warns(UserWarning, match="initialized yet"):
        df = table.frame(fake.invoke, N)
    assert list(df.columns) == list(table.names)
    assert df.isna().all().all()


def test_frame_returns_one_column_per_name():
    fake = _FakeFvs(TREES)
    TREES.set(fake.invoke, "dbh", np.array([1.0, 2.0, 3.0]), N)
    df = TREES.frame(fake.invoke, N)
    assert list(df.columns) == list(TREES.names)
    assert df["dbh"].tolist() == [1.0, 2.0, 3.0]

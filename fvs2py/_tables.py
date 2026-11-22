"""Stateless reads of FVS's in-memory output tables behind `FVS`.

Each function takes `invoke` (`FvsCore._invoke`). Names and text come back in
one buffer, each entry followed by a NUL. When a buffer is too small FVS returns
code 2 and reports the size it needs; tables can't change between two calls at
the same stop point, so one retry at that size always fits.
"""

from __future__ import annotations

import ctypes as ct
from collections.abc import Callable

import numpy as np
import pandas as pd

from fvs2py._attributes import Invoke
from fvs2py._routines import memory_table_policy

Buffers = list[ct.Array[ct.c_char]]
Lengths = list[ct.c_int]


def _grow(
    call: Callable[[Buffers, Lengths], int], *sizes: int
) -> tuple[Buffers, Lengths]:
    """Call `call` with buffers of `sizes`, retrying once at the sizes needed.

    `call` gets the buffers and their lengths (which FVS overwrites with the
    characters used or needed) and returns the routine's return code.
    """
    for _ in range(2):
        bufs = [ct.create_string_buffer(max(s, 1)) for s in sizes]
        lens = [ct.c_int(len(b)) for b in bufs]
        rc = call(bufs, lens)
        if rc != 2:
            break
        sizes = tuple(max(len(b), n.value) for b, n in zip(bufs, lens))
    memory_table_policy(rc)
    return bufs, lens


def _split0(buf: ct.Array[ct.c_char], n: int) -> list[str]:
    """Entries of a NUL-terminated list that uses `n` characters of `buf`."""
    return [s.decode() for s in buf.raw[:n].split(b"\0")[:-1]]


def table_names(invoke: Invoke) -> list[str]:
    """Names of the tables in the in-memory output database."""
    (buf,), (n,) = _grow(
        lambda b, n: invoke("fvsTableList", names=b[0], nch=n[0])["rtncode"],
        1024,
    )
    return _split0(buf, n.value)


def get_table(invoke: Invoke, name: str) -> pd.DataFrame:
    """Every row of table `name`, columns in table order."""
    # Every table routine takes the name and its length first.
    table = {"name": name.encode(), "nch": ct.c_int(len(name.encode()))}

    # 1. Size the table: row count, and how many columns FVS returns as numbers
    # (fvsTableNum) and how many as text (fvsTableTxt).
    dims = invoke("fvsTableDims", **table)
    nrow, nnum, ntxt = dims["nrow"], dims["nnum"], dims["ntxt"]
    ncol = nnum + ntxt

    # 2. Column names and declared SQL types, both in table order, plus istxt,
    # which FVS fills with 1 for each text column and 0 for each numeric one.
    # Names and types come back NUL-separated in two buffers; the starting
    # sizes are guesses, and `_grow` retries once if either is too small.
    istxt = np.zeros(ncol, dtype=np.intc)
    (cbuf, tbuf), (cn, tn) = _grow(
        lambda b, n: invoke(
            "fvsTableColumns",
            **table,
            ncol=ct.c_int(ncol),
            cols=b[0],
            ncolch=n[0],
            types=b[1],
            ntypch=n[1],
            istxt=istxt,
        ),
        32 * ncol,
        16 * ncol,
    )
    cols, types = _split0(cbuf, cn.value), _split0(tbuf, tn.value)

    # 3. The numeric columns only, as one (nrow, nnum) float64 array that FVS
    # fills in place. NULL comes back as NaN. The columns are in table order
    # among themselves, with the text columns skipped.
    num = np.full((nrow, nnum), np.nan)
    if nrow and nnum:
        invoke(
            "fvsTableNum",
            **table,
            row0=ct.c_int(1),
            nrows=ct.c_int(nrow),
            nnum=ct.c_int(nnum),
            values=num,
        )

    # 4. The text columns only, as one flat NUL-separated list: row 1's text
    # values, then row 2's, and so on. NULL comes back as "".
    txt: list[str] = []
    if nrow and ntxt:
        (buf,), (n,) = _grow(
            lambda b, n: invoke(
                "fvsTableTxt",
                **table,
                row0=ct.c_int(1),
                nrows=ct.c_int(nrow),
                ntxt=ct.c_int(ntxt),
                text=b[0],
                ntextch=n[0],
            ),
            16 * nrow * ntxt,
        )
        txt = _split0(buf, n.value)

    # 5. Interleave the two groups back into table order. Each iterator yields
    # one column at a time (transposing turns rows into columns); walking the
    # columns in table order, istxt says which group the next column comes
    # from. E.g. istxt [1, 0, 0, 1] takes text, numeric, numeric, text. Numeric
    # columns declared as an integer type (INT, INTEGER, ...) become nullable
    # Int64; the rest stay float64.
    nums = iter(num.T)
    txts = iter(np.array(txt, dtype=object).reshape(nrow, ntxt).T)
    return pd.DataFrame({
        c: next(txts)
        if is_txt
        else pd.array(next(nums), dtype="Int64" if "INT" in t else "float64")
        for c, t, is_txt in zip(cols, types, istxt, strict=True)
    })


def clear_table(invoke: Invoke, name: str) -> None:
    """Drop table `name` from the in-memory output database."""
    invoke(
        "fvsClearTable", name=name.encode(), nch=ct.c_int(len(name.encode()))
    )

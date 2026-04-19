"""Unit tests for ``fvs2py.keyfile`` — pure-Python, no FVS dependency."""

from __future__ import annotations

import importlib.resources

import pytest

from fvs2py.keyfile import (
    SINGLE_STAND_REQUIRED,
    count_keywords,
    validate_single_stand,
)

SO_KEYFILE = (
    importlib.resources.files("fvs2py.tests.keyfiles")
    .joinpath("SO.key")
    .read_text()
)


def test_count_keywords_counts_each_occurrence():
    text = "STDIDENT\nPROCESS\nSTOP\n"
    assert count_keywords(text) == {"STDIDENT": 1, "PROCESS": 1, "STOP": 1}


def test_count_keywords_is_case_insensitive():
    text = "stdident\nSTDIDENT\nStDiDeNt\n"
    assert count_keywords(text) == {"STDIDENT": 3}


def test_count_keywords_ignores_data_lines_starting_with_non_letters():
    text = "STDIDENT\n12345 TEST\n-999\n(I4,I4)\nSTOP\n"
    assert count_keywords(text) == {"STDIDENT": 1, "STOP": 1}


def test_count_keywords_accepts_keyword_followed_immediately_by_argument():
    text = "NUMCYCLE10.0\nSTOP\n"
    assert count_keywords(text) == {"NUMCYCLE": 1, "STOP": 1}


def test_count_keywords_truncates_runs_longer_than_ten_letters():
    """Column 1-10 is the keyword field; trailing letters stay in that field.

    An unusually long leading letter run is truncated to the first ten
    characters rather than rejected outright — FVS keyword names never exceed
    ten letters, so a longer run only appears in malformed or comment lines
    and we'd rather over-count a non-keyword token than miss a real one.
    """
    text = "ELEVENLETTERS\nSTOP\n"
    assert count_keywords(text) == {"ELEVENLETT": 1, "STOP": 1}


def test_count_keywords_handles_real_keyfile():
    counts = count_keywords(SO_KEYFILE)
    for required, expected in SINGLE_STAND_REQUIRED.items():
        assert counts[required] == expected


def test_validate_single_stand_accepts_real_keyfile():
    validate_single_stand(SO_KEYFILE)


def test_validate_single_stand_rejects_missing_stdident():
    text = SO_KEYFILE.replace("STDIDENT", "XXXXXXX1")
    with pytest.raises(ValueError, match="missing required keyword 'STDIDENT'"):
        validate_single_stand(text)


def test_validate_single_stand_rejects_multiple_stdident():
    text = SO_KEYFILE + "\n" + SO_KEYFILE
    with pytest.raises(ValueError, match="found 2 instances of 'STDIDENT'"):
        validate_single_stand(text)


def test_validate_single_stand_reports_every_failing_keyword():
    text = "NUMCYCLE 10\n"  # no STDIDENT, no PROCESS, no STOP
    with pytest.raises(ValueError, match="missing required keyword") as excinfo:
        validate_single_stand(text)
    msg = str(excinfo.value)
    for kw in SINGLE_STAND_REQUIRED:
        assert f"missing required keyword {kw!r}" in msg

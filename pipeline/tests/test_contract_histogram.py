import pytest
from pydantic import ValidationError

from statsboteval_pipeline.contract import Histogram, HistogramBin, dump_doc, ok, suppressed


def make_hist(**overrides):
    base = dict(
        unit="sessions",
        bins=[
            HistogramBin(lo=1, hi=1, cell=ok(214)),
            HistogramBin(lo=2, hi=3, cell=ok(96)),
            HistogramBin(lo=4, hi=7, cell=suppressed()),
            HistogramBin(lo=8, hi=None, cell=ok(11)),
        ],
        n_total=ok(327),
    )
    base.update(overrides)
    return Histogram(**base)


def test_valid_histogram_parses() -> None:
    assert len(make_hist().bins) == 4


def test_open_bin_only_last() -> None:
    with pytest.raises(ValidationError):
        make_hist(bins=[HistogramBin(lo=1, hi=None, cell=ok(1)), HistogramBin(lo=2, hi=3, cell=ok(1))])


def test_overlapping_bins_rejected() -> None:
    with pytest.raises(ValidationError):
        make_hist(bins=[HistogramBin(lo=1, hi=3, cell=ok(1)), HistogramBin(lo=3, hi=5, cell=ok(1))])


def test_hi_below_lo_rejected() -> None:
    with pytest.raises(ValidationError):
        make_hist(bins=[HistogramBin(lo=5, hi=2, cell=ok(1))])


def test_open_bin_serializes_hi_null() -> None:
    # exclude_none must NOT drop hi: null is the open-top-bin marker (contract §5).
    dumped = dump_doc(make_hist())
    assert dumped["bins"][-1]["hi"] is None


def test_summary_all_or_nothing() -> None:
    h = make_hist(summary={"status": "ok", "n_students": 74, "median": 2.0, "p25": 1.0, "p75": 4.0})
    dumped = dump_doc(h)
    assert dumped["summary"]["n_students"] == 74
    assert "mean" not in dumped["summary"]  # absent optionals are absent, not null
    h2 = make_hist(summary={"status": "suppressed"})
    assert dump_doc(h2)["summary"] == {"status": "suppressed"}

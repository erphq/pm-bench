"""Tests for the stdlib XES parser."""
from __future__ import annotations

import datetime as dt
import gzip
import textwrap
from pathlib import Path

import pytest

from pm_bench.xes import read_xes_log


def _xes(body: str) -> str:
    """Wrap a body in the standard XES envelope."""
    return textwrap.dedent(
        f"""<?xml version="1.0" encoding="UTF-8"?>
        <log xmlns="http://www.xes-standard.org/" xes.version="2.0">
        {body}
        </log>
        """
    ).strip()


def test_simple_two_case_log(tmp_path: Path) -> None:
    p = tmp_path / "log.xes"
    p.write_text(
        _xes(
            """
            <trace>
              <string key="concept:name" value="case_1"/>
              <event>
                <string key="concept:name" value="received"/>
                <date key="time:timestamp" value="2024-01-01T00:00:00.000+00:00"/>
              </event>
              <event>
                <string key="concept:name" value="paid"/>
                <date key="time:timestamp" value="2024-01-01T01:00:00.000+00:00"/>
              </event>
            </trace>
            <trace>
              <string key="concept:name" value="case_2"/>
              <event>
                <string key="concept:name" value="received"/>
                <date key="time:timestamp" value="2024-02-01T00:00:00.000+00:00"/>
              </event>
            </trace>
            """
        )
    )
    events = read_xes_log(p)
    assert len(events) == 3
    assert events[0] == ("case_1", "received", dt.datetime(2024, 1, 1, 0, 0))
    assert events[1] == ("case_1", "paid", dt.datetime(2024, 1, 1, 1, 0))
    assert events[2] == ("case_2", "received", dt.datetime(2024, 2, 1, 0, 0))


def test_xes_gz_round_trip(tmp_path: Path) -> None:
    """Real BPI logs ship gzipped; the parser must accept .xes.gz."""
    p = tmp_path / "log.xes.gz"
    body = _xes(
        """
        <trace>
          <string key="concept:name" value="c1"/>
          <event>
            <string key="concept:name" value="a"/>
            <date key="time:timestamp" value="2024-01-01T00:00:00Z"/>
          </event>
        </trace>
        """
    )
    with gzip.open(p, "wt", encoding="utf-8") as f:
        f.write(body)
    events = read_xes_log(p)
    assert events == [("c1", "a", dt.datetime(2024, 1, 1, 0, 0))]


def test_namespace_tolerance_no_xmlns(tmp_path: Path) -> None:
    """Some hand-edited XES files omit the xmlns declaration."""
    p = tmp_path / "no-ns.xes"
    p.write_text(
        textwrap.dedent(
            """<?xml version="1.0" encoding="UTF-8"?>
            <log>
              <trace>
                <string key="concept:name" value="c1"/>
                <event>
                  <string key="concept:name" value="a"/>
                  <date key="time:timestamp" value="2024-01-01T00:00:00"/>
                </event>
              </trace>
            </log>
            """
        ).strip()
    )
    events = read_xes_log(p)
    assert events == [("c1", "a", dt.datetime(2024, 1, 1, 0, 0))]


def test_tz_aware_normalised_to_utc(tmp_path: Path) -> None:
    """A `+05:00` timestamp must become its UTC instant (naive)."""
    p = tmp_path / "tz.xes"
    p.write_text(
        _xes(
            """
            <trace>
              <string key="concept:name" value="c1"/>
              <event>
                <string key="concept:name" value="a"/>
                <date key="time:timestamp" value="2024-01-01T05:00:00+05:00"/>
              </event>
            </trace>
            """
        )
    )
    events = read_xes_log(p)
    # 05:00 +05:00 = 00:00 UTC
    assert events[0][2] == dt.datetime(2024, 1, 1, 0, 0)
    assert events[0][2].tzinfo is None


def test_missing_activity_raises(tmp_path: Path) -> None:
    p = tmp_path / "bad.xes"
    p.write_text(
        _xes(
            """
            <trace>
              <string key="concept:name" value="c1"/>
              <event>
                <date key="time:timestamp" value="2024-01-01T00:00:00"/>
              </event>
            </trace>
            """
        )
    )
    with pytest.raises(ValueError, match="missing required `concept:name`"):
        read_xes_log(p)


def test_missing_timestamp_raises(tmp_path: Path) -> None:
    p = tmp_path / "bad.xes"
    p.write_text(
        _xes(
            """
            <trace>
              <string key="concept:name" value="c1"/>
              <event>
                <string key="concept:name" value="a"/>
              </event>
            </trace>
            """
        )
    )
    with pytest.raises(ValueError, match="missing required `time:timestamp`"):
        read_xes_log(p)


def test_missing_case_id_raises(tmp_path: Path) -> None:
    """An event outside any trace, or a trace without a concept:name, is
    a malformed XES log."""
    p = tmp_path / "bad.xes"
    p.write_text(
        _xes(
            """
            <trace>
              <event>
                <string key="concept:name" value="a"/>
                <date key="time:timestamp" value="2024-01-01T00:00:00"/>
              </event>
            </trace>
            """
        )
    )
    with pytest.raises(ValueError, match="case_id"):
        read_xes_log(p)


def test_malformed_xml_raises_clean_error(tmp_path: Path) -> None:
    p = tmp_path / "garbage.xes"
    p.write_text("<log><trace>not closed")
    with pytest.raises(ValueError, match="malformed XML"):
        read_xes_log(p)


def test_bad_timestamp_raises(tmp_path: Path) -> None:
    p = tmp_path / "bad.xes"
    p.write_text(
        _xes(
            """
            <trace>
              <string key="concept:name" value="c1"/>
              <event>
                <string key="concept:name" value="a"/>
                <date key="time:timestamp" value="not-a-date"/>
              </event>
            </trace>
            """
        )
    )
    with pytest.raises(ValueError, match="bad timestamp"):
        read_xes_log(p)


def test_full_pipeline_through_xes_path(tmp_path: Path) -> None:
    """`pm-bench split path/to/log.xes` should run end-to-end through
    the full pipeline now that XES is in `_load_events`."""
    from click.testing import CliRunner

    from pm_bench.cli import main

    p = tmp_path / "log.xes"
    # 6 cases, 2 events each — enough for a 3/1/2 train/val/test split.
    traces = []
    for i in range(6):
        traces.append(
            f"""<trace>
              <string key="concept:name" value="c{i}"/>
              <event>
                <string key="concept:name" value="start"/>
                <date key="time:timestamp" value="2024-01-{i+1:02d}T00:00:00"/>
              </event>
              <event>
                <string key="concept:name" value="end"/>
                <date key="time:timestamp" value="2024-01-{i+1:02d}T01:00:00"/>
              </event>
            </trace>"""
        )
    p.write_text(_xes("\n".join(traces)))
    r = CliRunner().invoke(main, ["split", str(p)])
    assert r.exit_code == 0, r.output
    assert "train" in r.output


def test_clear_error_when_xes_path_missing(tmp_path: Path) -> None:
    """A typo'd .xes path must produce a clean exit-1 message."""
    from click.testing import CliRunner

    from pm_bench.cli import main

    r = CliRunner().invoke(main, ["split", str(tmp_path / "no-such.xes")])
    assert r.exit_code == 1
    assert "no such file" in r.output

"""XES event-log parser.

XES is the IEEE 1849-2016 standard for process event logs. Every BPI
Challenge log on 4TU is shipped as XES (typically gzipped: `.xes.gz`).
Despite XES's verbose attribute model, pm-bench only needs three values
per event — `case_id`, `activity`, `timestamp` — so a 100-line stdlib
parser is enough. Avoiding a `pm4py` dependency keeps the install
footprint at zero new packages.

XES structure (simplified):

    <log>
      <trace>
        <string key="concept:name" value="case_42"/>      <!-- case_id -->
        <event>
          <string key="concept:name" value="activity_A"/>  <!-- activity -->
          <date key="time:timestamp" value="2024-01-01T00:00:00.000+00:00"/>
        </event>
        <event>...</event>
      </trace>
      <trace>...</trace>
    </log>

The parser is namespace-tolerant (XES files in the wild sometimes
declare `xmlns="http://www.xes-standard.org/"`, sometimes don't), uses
`xml.etree.ElementTree.iterparse` so memory stays bounded on 100MB+
logs, and surfaces malformed XML as a clean `ValueError` rather than
the underlying `ExpatError`.
"""
from __future__ import annotations

import gzip
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

from pm_bench.split import Event

# XES has the namespace `http://www.xes-standard.org/`. Some files
# declare it on the root, some don't. ElementTree exposes namespaced
# tags as `{ns}tag`; we strip the namespace at parse time so the rest
# of the parser doesn't care.
_CASE_KEY = "concept:name"
_ACTIVITY_KEY = "concept:name"
_TIMESTAMP_KEY = "time:timestamp"


def _strip_ns(tag: str) -> str:
    """`{http://...}trace` → `trace`."""
    return tag.split("}", 1)[1] if "}" in tag else tag


def _parse_attr(elem: ET.Element) -> tuple[str, str] | None:
    """An XES attribute is `<string key="..." value="..."/>` (or `date`,
    `int`, `float`, etc.). Returns the (key, value) pair or None if
    the element isn't an attribute."""
    tag = _strip_ns(elem.tag)
    if tag in ("string", "date", "int", "float", "boolean", "id"):
        key = elem.get("key")
        value = elem.get("value")
        if key is not None and value is not None:
            return (key, value)
    return None


def _parse_timestamp(value: str) -> datetime:
    """Parse an XES `date` value. The standard is ISO 8601; common
    variants include trailing `Z`, fractional seconds, and `+00:00`
    offsets. `datetime.fromisoformat` handles all of these on 3.11+.

    Tz-aware results are normalized to UTC and stripped, mirroring the
    CSV ingest path (so split / duration arithmetic doesn't trip on
    mixed-tz inputs).
    """
    ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if ts.tzinfo is not None:
        ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
    return ts


def read_xes_log(path: str | Path) -> list[Event]:
    """Read an XES (or `.xes.gz`) event log into Event tuples.

    Streams via `iterparse` so 100 MB logs don't load entirely into
    memory. Yields events in the order they appear in the file (which
    is the canonical traversal — XES doesn't mandate timestamp ordering
    at the file level; downstream `case_chrono_split` and
    `extract_prefixes` re-sort by timestamp anyway).

    Raises `ValueError` with file:line context on malformed XML or a
    missing required attribute (case_id, activity, timestamp).
    """
    p = Path(path)
    opener = gzip.open if str(p).endswith(".gz") else open
    out: list[Event] = []
    current_case: str | None = None
    n_events_seen = 0

    try:
        with opener(p, "rb") as f:
            # `events=("start", "end")` lets us track trace boundaries;
            # we collect attribute strings inside <event>, emit on
            # </event>.
            current_event_attrs: dict[str, str] | None = None
            for event_kind, elem in ET.iterparse(f, events=("start", "end")):
                tag = _strip_ns(elem.tag)

                if event_kind == "start":
                    if tag == "trace":
                        current_case = None  # reset; populated by trace-level attrs
                    elif tag == "event":
                        current_event_attrs = {}

                elif event_kind == "end":
                    if tag in ("string", "date", "int", "float", "boolean", "id"):
                        kv = _parse_attr(elem)
                        if kv is None:
                            elem.clear()
                            continue
                        key, value = kv
                        # Trace-level concept:name comes before any <event>;
                        # event-level attributes come inside <event>.
                        if current_event_attrs is not None:
                            current_event_attrs[key] = value
                        elif current_case is None and key == _CASE_KEY:
                            current_case = value

                    elif tag == "event":
                        if current_event_attrs is None:
                            elem.clear()
                            continue
                        n_events_seen += 1
                        if current_case is None:
                            raise ValueError(
                                f"{path}: event #{n_events_seen} appears outside a trace "
                                "with a `concept:name` (case_id) attribute"
                            )
                        activity = current_event_attrs.get(_ACTIVITY_KEY)
                        ts_str = current_event_attrs.get(_TIMESTAMP_KEY)
                        if activity is None:
                            raise ValueError(
                                f"{path}: event #{n_events_seen} (case {current_case!r}) "
                                "missing required `concept:name` (activity) attribute"
                            )
                        if ts_str is None:
                            raise ValueError(
                                f"{path}: event #{n_events_seen} (case {current_case!r}) "
                                "missing required `time:timestamp` attribute"
                            )
                        try:
                            ts = _parse_timestamp(ts_str)
                        except ValueError as exc:
                            raise ValueError(
                                f"{path}: event #{n_events_seen} (case {current_case!r}) "
                                f"has bad timestamp {ts_str!r}"
                            ) from exc
                        out.append((current_case, activity, ts))
                        current_event_attrs = None
                        # Free memory aggressively — XES traces can be
                        # millions of events.
                        elem.clear()

                    elif tag == "trace":
                        current_case = None
                        elem.clear()
    except ET.ParseError as exc:
        raise ValueError(f"{path}: malformed XML — {exc}") from exc

    return out

"""pm-bench - the open process-mining benchmark."""
from __future__ import annotations

import csv as _csv
import sys as _sys

# Lift the per-field CSV size limit module-wide. Default is 128 KiB,
# which a real BPI dataset with verbose activity labels (or
# pipe-joined prefix columns from long traces) can blow through with
# a cryptic `_csv.Error: field larger than field limit` from
# csv.DictReader. 2 GiB is plenty for any realistic log and stays
# under int32 ceilings on 32-bit platforms.
_csv.field_size_limit(min(_sys.maxsize, 2**31 - 1))

__version__ = "0.1.0"

from pm_bench.predictions import (  # noqa: E402
    Prediction,
    read_predictions_csv,
    write_predictions_csv,
)
from pm_bench.prefixes import (  # noqa: E402
    OutcomeTarget,
    Prefix,
    TimeTarget,
    extract_outcome_targets,
    extract_prefixes,
    extract_remaining_time_targets,
    read_outcome_targets_csv,
    read_prefixes_csv,
    read_time_targets_csv,
    write_outcome_targets_csv,
    write_prefixes_csv,
    write_time_targets_csv,
)
from pm_bench.registry import Dataset, get_dataset, load_registry  # noqa: E402
from pm_bench.score import (  # noqa: E402
    BottleneckScore,
    ConformanceScore,
    NextEventScore,
    OutcomeScore,
    RemainingTimeScore,
    score_bottleneck,
    score_conformance,
    score_next_event,
    score_outcome,
    score_remaining_time,
)
from pm_bench.split import Event, Split, case_chrono_split  # noqa: E402

__all__ = [
    "BottleneckScore",
    "ConformanceScore",
    "Dataset",
    "Event",
    "NextEventScore",
    "OutcomeScore",
    "OutcomeTarget",
    "Prediction",
    "Prefix",
    "RemainingTimeScore",
    "Split",
    "TimeTarget",
    "case_chrono_split",
    "extract_outcome_targets",
    "extract_prefixes",
    "extract_remaining_time_targets",
    "get_dataset",
    "load_registry",
    "read_outcome_targets_csv",
    "read_predictions_csv",
    "read_prefixes_csv",
    "read_time_targets_csv",
    "score_bottleneck",
    "score_conformance",
    "score_next_event",
    "score_outcome",
    "score_remaining_time",
    "write_outcome_targets_csv",
    "write_predictions_csv",
    "write_prefixes_csv",
    "write_time_targets_csv",
]

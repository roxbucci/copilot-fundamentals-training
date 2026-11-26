#!/usr/bin/env python3
"""
Quick log triage utility
────────────────────────
  • Accepts   *.log  or  *.log.gz
  • Filters   last N minutes (sliding window)
  • Tallies   (status‑code, endpoint) pairs
  • Optional  --status 499,321 for focused searching

  A noisy incident page reveals a spike in 321 or 499 errors, but the observability stack is lagging. You need a quick, local log sweep to spot patterns and counts.
"""

from pathlib import Path
from datetime import datetime, timedelta, timezone
import argparse
import csv
import gzip
import re
import sys
from collections import Counter
from typing import Iterable, Tuple

_LOG_LINE_RE = re.compile(
    r'^\S+\s+\S+\s+\S+\s+\[(?P<timestamp>[^\]]+)\]\s+'
    r'"\S+\s+(?P<path>\S+)\s+HTTP/[0-9]+(?:\.[0-9]+)?"\s+'
    r'(?P<status>[0-9]{3})\s+(?:[0-9]+|-)(?:\s+.*)?$'
)

# ---------------------------------------------------------------------------
# ✨ Log triage functions ✨
# ---------------------------------------------------------------------------

def read_lines(file_path: Path) -> Iterable[str]:
    """Open plain or gzipped log file and yield each line (stripped)."""
    opener = gzip.open if file_path.suffix == ".gz" else open
    with opener(file_path, "rt", encoding="utf-8") as log_file:
        for line in log_file:
            yield line.strip()


def parse_line(line: str) -> Tuple[datetime, int, str] | None:
    """Return (timestamp_utc, status_code_int, url_path) or None if malformed."""
    match = _LOG_LINE_RE.fullmatch(line.rstrip("\r\n"))
    if match is None:
        return None

    try:
        timestamp = datetime.strptime(
            match.group("timestamp"), "%d/%b/%Y:%H:%M:%S %z"
        ).astimezone(timezone.utc)
    except ValueError:
        return None

    return timestamp, int(match.group("status")), match.group("path")


def triage(
    lines: Iterable[str],
    minutes: int,
    wanted_status: set[int] | None
) -> Counter[Tuple[int, str]]:
    """Aggregate counts for lines within the window and matching status filter."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=minutes)
    counter: Counter[Tuple[int, str]] = Counter()
    for line in lines:
        parsed = parse_line(line)
        if parsed is None:
            continue
        timestamp, status, path = parsed
        if cutoff <= timestamp <= now:
            if wanted_status is None or status in wanted_status:
                counter[(status, path)] += 1
    return counter


def render(counter: Counter[Tuple[int, str]], top: int) -> None:
    """Pretty‑print a Markdown‑style table of the top offenders."""
    print("Rank | Status | Path | Hits")
    print("-----|--------|------|-----")
    for rank, ((status, path), hits) in enumerate(counter.most_common(top), start=1):
        print(f"{rank} | {status} | {path} | {hits}")


def main() -> None:
    """Wire everything together with argparse CLI options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True, help="Plain or gzipped log file")
    parser.add_argument("--minutes", type=int, default=15, help="Window in minutes (default: 15)")
    parser.add_argument("--status", help="Comma-separated status codes, e.g. 499,321")
    parser.add_argument("--top", type=int, default=10, help="Maximum rows to display (default: 10)")
    parser.add_argument("--output", type=Path, help="Export displayed results to a UTF-8 CSV file")
    args = parser.parse_args()
    if args.minutes <= 0 or args.top <= 0:
        parser.error("--minutes and --top must be positive integers")
    if args.output is not None and args.output.resolve() == args.file.resolve():
        parser.error("--output must be different from the input file")

    wanted_status = None
    if args.status is not None:
        try:
            wanted_status = {int(code.strip()) for code in args.status.split(",")}
        except ValueError:
            parser.error("--status must be a comma-separated list of integers")

    try:
        counter = triage(read_lines(args.file), args.minutes, wanted_status)
    except (OSError, EOFError, UnicodeError) as error:
        parser.error(f"Cannot read {args.file}: {error}")
    if args.output is not None:
        try:
            with args.output.open("w", encoding="utf-8", newline="") as output_file:
                writer = csv.writer(output_file)
                writer.writerow(["Rank", "Status", "Path", "Hits"])
                writer.writerows(
                    (rank, status, path, hits)
                    for rank, ((status, path), hits)
                    in enumerate(counter.most_common(args.top), start=1)
                )
        except (OSError, UnicodeError) as error:
            parser.error(f"Cannot write {args.output}: {error}")
    render(counter, args.top)
    if not counter:
        print("No matching log entries found.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

# ---------------------------------------------------------------------------
# 📝 Copilot prompts used to implement the functions
# ---------------------------------------------------------------------------
# read_lines prompt:
#   "Implement read_lines(file_path) so it transparently handles .log or .log.gz,
#    opens in text mode (UTF‑8), and yields one stripped line at a time."

# parse_line prompt:
#   "Use a compiled regex for common/combined log format; pull timestamp,
#    status, and path. Convert the timestamp '[15/Jul/2025:14:23:41 +0000]'
#    to a timezone‑aware UTC datetime. Return None if the line doesn't match."

# triage prompt:
#   "Stream through lines, parse each; skip malformed. Keep only entries whose
#    timestamp is within <minutes> of datetime.utcnow() and, if wanted_status
#    is provided, whose status is in that set. Use a Counter keyed by
#    (status_code, path)."

# render prompt:
#   "Print the top <top> (status, path) pairs from the Counter in descending
#    order of hits, formatted as a Markdown table: Rank | Status | Path | Hits."

# main prompt:
#   "Add argparse arguments:
#       --file (required)
#       --minutes (int, default 15)
#       --status  (comma‑separated list of ints, optional)
#       --top     (int, default 10)
#       --output  (optional CSV output path)
#    Parse args, build wanted_status set, call triage(), then render().
#    Exit with status‑code 1 if no matches were found."

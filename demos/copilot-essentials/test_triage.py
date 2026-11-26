import csv
import gzip
import io
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import triage


def log_line(timestamp, status=499, path="/login"):
    return (
        f'127.0.0.1 - - [{timestamp:%d/%b/%Y:%H:%M:%S %z}] '
        f'"GET {path} HTTP/1.1" {status} 123'
    )


class TriageTests(unittest.TestCase):
    def test_existing_sample_log(self):
        sample = Path(__file__).with_name("sample_access.log.gz")
        now = datetime(2025, 7, 15, 17, 51, 16, tzinfo=timezone.utc)
        expected = {
            (321, "/admin"): 2,
            (321, "/api/v1/orders"): 1,
            (321, "/api/v1/products"): 2,
            (321, "/health"): 1,
            (321, "/login"): 1,
            (321, "/logout"): 3,
            (321, "/reports/summary"): 3,
            (321, "/static/app.css"): 2,
            (321, "/static/app.js"): 1,
            (499, "/api/v1/orders"): 4,
            (499, "/api/v1/products"): 1,
            (499, "/api/v1/users"): 3,
            (499, "/health"): 1,
            (499, "/login"): 4,
            (499, "/logout"): 3,
            (499, "/reports/summary"): 2,
            (499, "/static/app.css"): 1,
            (499, "/static/app.js"): 3,
        }
        output = io.StringIO()
        argv = [
            "triage.py", "--file", str(sample), "--minutes", "15",
            "--status", "499,321", "--top", "100",
        ]
        with patch.object(triage, "datetime") as clock:
            clock.now.return_value = now
            clock.strptime.side_effect = datetime.strptime
            with patch.object(sys, "argv", argv), redirect_stdout(output):
                triage.main()
        rows = output.getvalue().splitlines()
        self.assertEqual(rows[:2], [
            "Rank | Status | Path | Hits",
            "-----|--------|------|-----",
        ])
        actual = {}
        hits_in_order = []
        for rank, row in enumerate(rows[2:], start=1):
            position, status, path, hits = (cell.strip() for cell in row.split("|"))
            self.assertEqual(int(position), rank)
            actual[(int(status), path)] = int(hits)
            hits_in_order.append(int(hits))
        self.assertEqual(len(rows[2:]), len(expected))
        self.assertEqual(actual, expected)
        self.assertEqual(hits_in_order, sorted(hits_in_order, reverse=True))

    def test_window_boundaries_and_status_filter(self):
        now = datetime(2026, 11, 26, 10, 0, tzinfo=timezone.utc)
        lines = [
            "malformed",
            log_line(now - timedelta(minutes=15)),
            log_line(now),
            log_line(now - timedelta(minutes=15, seconds=1)),
            log_line(now + timedelta(seconds=1)),
            log_line(now, 321, "/api"),
            log_line(now, 200),
        ]
        with patch.object(triage, "datetime") as clock:
            clock.now.return_value = now
            clock.strptime.side_effect = datetime.strptime
            self.assertEqual(
                triage.triage(iter(lines), 15, {499, 321}),
                Counter({(499, "/login"): 2, (321, "/api"): 1}),
            )
            self.assertEqual(sum(triage.triage(iter(lines), 15, None).values()), 4)
            self.assertEqual(triage.triage(iter(lines), 15, set()), Counter())

    def test_render_orders_and_limits_rows(self):
        output = io.StringIO()
        with redirect_stdout(output):
            triage.render(Counter({(321, "/api"): 1, (499, "/login"): 3}), 1)
        self.assertEqual(
            output.getvalue().splitlines(),
            [
                "Rank | Status | Path | Hits",
                "-----|--------|------|-----",
                "1 | 499 | /login | 3",
            ],
        )

    def test_cli_plain_and_gzip(self):
        now = datetime.now(timezone.utc)
        content = "\n".join([
            log_line(now - timedelta(seconds=5)),
            log_line(now - timedelta(seconds=10), 321, "/api"),
            log_line(now - timedelta(minutes=30)),
        ])
        with tempfile.TemporaryDirectory() as directory:
            for suffix in (".log", ".log.gz"):
                with self.subTest(suffix=suffix):
                    path = Path(directory) / ("access" + suffix)
                    opener = gzip.open if suffix.endswith(".gz") else open
                    with opener(path, "wt", encoding="utf-8") as stream:
                        stream.write(content)
                    result = self.run_cli("--file", str(path), "--status", "499,321", "--top", "1")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(
                        result.stdout.splitlines(),
                        [
                            "Rank | Status | Path | Hits",
                            "-----|--------|------|-----",
                            "1 | 499 | /login | 1",
                        ],
                    )
                    result = self.run_cli("--file", str(path), "--status", "503")
                    self.assertEqual(result.returncode, 1)
                    self.assertIn("No matching log entries", result.stderr)

    def test_cli_reports_invalid_arguments_and_unreadable_files(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = str(Path(directory) / "missing.log")
            for options, message in (
                ([], "Cannot read"),
                (["--minutes", "0"], "positive integers"),
                (["--top", "-1"], "positive integers"),
                (["--status", "499,invalid"], "comma-separated list"),
            ):
                with self.subTest(options=options):
                    result = self.run_cli("--file", missing, *options)
                    self.assertEqual(result.returncode, 2)
                    self.assertIn(message, result.stderr)

    def test_cli_exports_csv(self):
        now = datetime.now(timezone.utc) - timedelta(seconds=5)
        content = "\n".join([
            log_line(now, 499, "/caf\u00e9,orders"),
            log_line(now, 499, "/caf\u00e9,orders"),
            log_line(now, 321, "/login"),
            log_line(now, 200, "/health"),
            log_line(now - timedelta(minutes=30), 499, "/old"),
        ])
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "access.log.gz"
            target = Path(directory) / "results.csv"
            with gzip.open(source, "wt", encoding="utf-8") as stream:
                stream.write(content)
            for status, expected_code, expected_rows in (
                ("499,321", 0, [["1", "499", "/caf\u00e9,orders", "2"]]),
                ("503", 1, []),
            ):
                with self.subTest(status=status):
                    result = self.run_cli(
                        "--file", str(source), "--status", status,
                        "--top", "1", "--output", str(target),
                    )
                    self.assertEqual(result.returncode, expected_code, result.stderr)
                    self.assertIn("Rank | Status | Path | Hits", result.stdout)
                    with target.open(encoding="utf-8", newline="") as stream:
                        self.assertEqual(
                            list(csv.reader(stream)),
                            [["Rank", "Status", "Path", "Hits"], *expected_rows],
                        )

    def test_cli_reports_invalid_csv_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "access.log"
            content = log_line(datetime.now(timezone.utc) - timedelta(seconds=5))
            source.write_text(content, encoding="utf-8")
            for target, message in (
                (Path(directory) / "missing" / "results.csv", "Cannot write"),
                (source, "different from the input file"),
            ):
                with self.subTest(target=target):
                    result = self.run_cli("--file", str(source), "--output", str(target))
                    self.assertEqual(result.returncode, 2)
                    self.assertIn(message, result.stderr)
                    self.assertEqual(source.read_text(encoding="utf-8"), content)

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-B", str(Path(triage.__file__)), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()

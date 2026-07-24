#!/usr/bin/env python3
"""Fail loudly if official metrics, report, framework, or package diverge."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pypdf import PdfReader


ORIGINAL_BACKTESTER_BLOB = "3b94f9749fb64e4fe271fae28d16628ea9fe2519"


def git_blob_id(path: Path) -> str:
    content = path.read_bytes().replace(b"\r\n", b"\n")
    header = f"blob {len(content)}\0".encode()
    return hashlib.sha1(header + content).hexdigest()


def main() -> int:
    project = Path(__file__).resolve().parent
    root = project.parent
    official = json.loads(
        (project / "results" / "organizer" / "metrics.json").read_text(
            encoding="utf-8"
        )
    )
    research = json.loads(
        (project / "results" / "research" / "metrics.json").read_text(
            encoding="utf-8"
        )
    )
    pdf = project / "SatoshiFlow_Report.pdf"
    reader = PdfReader(pdf)
    assert len(reader.pages) == 3, "report must be exactly three pages"
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "PROVISIONAL" not in text.upper()

    expected_text = (
        f"${official['final_capital']:,.2f}",
        f"{100 * official['net_return']:.2f}%",
        f"{official['sharpe_ratio']:.3f}",
        f"{official['maximum_drawdown_percentage']:.2f}%",
        f"{official['win_rate_percentage']:.2f}%",
        str(official["total_trades"]),
        f"${official['total_brokerage']:,.2f}",
        f"{official['benchmark_return_percentage']:.2f}%",
        official["dataset_sha256"],
        f"${research['final_equity']:,.2f}",
        f"{100 * research['max_drawdown']:.2f}%",
    )
    for value in expected_text:
        assert value in text, f"PDF is missing metrics-derived value: {value}"

    submission = root / "SUBMIT_THESE"
    assert sorted(item.name for item in submission.iterdir()) == [
        "SatoshiFlow_Report.pdf",
        "main.py",
    ]
    project_main = (project / "main.py").read_bytes()
    submission_main = (submission / "main.py").read_bytes()
    assert submission_main == project_main
    assert b"from backtester import BackTester" in submission_main
    assert (submission / "SatoshiFlow_Report.pdf").read_bytes() == pdf.read_bytes()
    assert git_blob_id(project / "backtester.py") == ORIGINAL_BACKTESTER_BLOB
    assert all(
        (
            official["lookahead_check"],
            official["signal_shift_check"],
            official["signal_validity_check"],
            official["organizer_backtester_check"],
            official["reproducibility_check"],
            research["lookahead_check"],
            research["next_bar_execution_check"],
            research["reproducibility_check"],
        )
    )
    assert not any(
        child.is_file() for child in (project / "results").iterdir()
    ), "stale result files remain outside organizer/research directories"
    print("PDF METRICS CHECK: PASS")
    print("FRAMEWORK INTEGRITY CHECK: PASS")
    print("SUBMISSION CONTENTS CHECK: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

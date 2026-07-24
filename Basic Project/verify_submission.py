#!/usr/bin/env python3
"""Fail loudly if the generated report or submission package is inconsistent."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pypdf import PdfReader


ORIGINAL_BACKTESTER_BLOB = "3b94f9749fb64e4fe271fae28d16628ea9fe2519"


def git_blob_id(path: Path) -> str:
    # Git's text filter stores LF in the blob even on a CRLF Windows checkout.
    content = path.read_bytes().replace(b"\r\n", b"\n")
    header = f"blob {len(content)}\0".encode()
    return hashlib.sha1(header + content).hexdigest()


def main() -> int:
    project = Path(__file__).resolve().parent
    root = project.parent
    metrics = json.loads(
        (project / "results" / "metrics.json").read_text(encoding="utf-8")
    )
    pdf = project / "SatoshiFlow_Report.pdf"
    reader = PdfReader(pdf)
    assert len(reader.pages) == 3, "report must be exactly three pages"
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    expected_text = (
        f"${metrics['final_equity']:,.2f}",
        f"{100 * metrics['net_return']:.2f}%",
        f"{metrics['sharpe_ratio']:.3f}",
        f"{100 * metrics['max_drawdown']:.2f}%",
        f"{metrics['win_rate']:.2f}%",
        str(metrics["total_trades"]),
        f"${metrics['total_brokerage']:,.2f}",
        f"{100 * metrics['buy_and_hold_return']:.2f}%",
        metrics["dataset_sha256"],
    )
    for value in expected_text:
        assert value in text, f"PDF is missing metrics-derived value: {value}"

    submission = root / "SUBMIT_THESE"
    assert sorted(item.name for item in submission.iterdir()) == [
        "SatoshiFlow_Report.pdf",
        "main.py",
    ]
    assert (submission / "main.py").read_bytes() == (project / "main.py").read_bytes()
    assert (submission / "SatoshiFlow_Report.pdf").read_bytes() == pdf.read_bytes()
    assert git_blob_id(project / "backtester.py") == ORIGINAL_BACKTESTER_BLOB
    assert all(
        (
            metrics["lookahead_check"],
            metrics["next_bar_execution_check"],
            metrics["reproducibility_check"],
        )
    )
    print("PDF METRICS CHECK: PASS")
    print("FRAMEWORK INTEGRITY CHECK: PASS")
    print("SUBMISSION CONTENTS CHECK: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Generate the organizer-led report and exact two-file submission package."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


NAVY = colors.HexColor("#102A43")
BLUE = colors.HexColor("#155EEF")
MUTED = colors.HexColor("#475467")
LIGHT = colors.HexColor("#F2F4F7")
AMBER = colors.HexColor("#B54708")


def money(value: float) -> str:
    return f"${value:,.2f}"


def footer(canvas, document) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D0D5DD"))
    canvas.line(0.62 * inch, 0.45 * inch, 7.88 * inch, 0.45 * inch)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(
        0.62 * inch,
        0.27 * inch,
        "SatoshiFlow | Organizer-compatible BTC/USD backtest",
    )
    canvas.drawRightString(
        7.88 * inch, 0.27 * inch, f"Page {document.page}"
    )
    canvas.restoreState()


def styled_table(rows: list[list[str]], body: ParagraphStyle) -> Table:
    rendered = [
        rows[0],
        *[[Paragraph(str(cell), body) for cell in row] for row in rows[1:]],
    ]
    table = Table(rendered, colWidths=[2.75 * inch, 4.10 * inch], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D0D5DD")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def official_metrics_table(metrics: dict, body: ParagraphStyle) -> Table:
    return styled_table(
        [
            ["Official organizer metric", "Value"],
            [
                "Initial / final capital",
                f"{money(metrics['initial_capital'])} / "
                f"{money(metrics['final_capital'])}",
            ],
            ["Net profit", money(metrics["net_profit"])],
            ["Net return", f"{100 * metrics['net_return']:.2f}%"],
            ["Sharpe ratio", f"{metrics['sharpe_ratio']:.3f}"],
            [
                "Maximum drawdown",
                f"{metrics['maximum_drawdown_percentage']:.2f}%",
            ],
            ["Win rate", f"{metrics['win_rate_percentage']:.2f}%"],
            ["Completed trades", str(metrics["total_trades"])],
            ["Framework brokerage deducted", money(metrics["total_brokerage"])],
            [
                "Buy-and-hold benchmark",
                f"{metrics['benchmark_return_percentage']:.2f}%",
            ],
        ],
        body,
    )


def research_metrics_table(metrics: dict, body: ParagraphStyle) -> Table:
    return styled_table(
        [
            ["Independent robustness metric", "Value"],
            ["Final equity", money(metrics["final_equity"])],
            ["Net return", f"{100 * metrics['net_return']:.2f}%"],
            ["Sharpe ratio", f"{metrics['sharpe_ratio']:.3f}"],
            ["Mark-to-market drawdown", f"{100 * metrics['max_drawdown']:.2f}%"],
            ["Win rate", f"{metrics['win_rate']:.2f}%"],
            ["Completed trades", str(metrics["total_trades"])],
            ["Two-sided brokerage", money(metrics["total_brokerage"])],
        ],
        body,
    )


def build_pdf(
    official: dict,
    research: dict,
    organizer_results: Path,
    research_results: Path,
    output: Path,
) -> None:
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.1,
        leading=11.7,
        textColor=NAVY,
        spaceAfter=5,
    )
    title = ParagraphStyle(
        "Title",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=26,
        leading=30,
        alignment=TA_CENTER,
        textColor=NAVY,
        spaceAfter=7,
    )
    subtitle = ParagraphStyle(
        "Subtitle",
        parent=body,
        fontSize=11,
        leading=14,
        alignment=TA_CENTER,
        textColor=MUTED,
        spaceAfter=15,
    )
    heading = ParagraphStyle(
        "Heading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13.2,
        leading=16,
        textColor=BLUE,
        spaceBefore=5,
        spaceAfter=5,
    )
    small = ParagraphStyle(
        "Small", parent=body, fontSize=8.0, leading=10.0, textColor=MUTED
    )
    note = ParagraphStyle(
        "Note",
        parent=body,
        borderColor=colors.HexColor("#F79009"),
        borderWidth=0.7,
        borderPadding=7,
        backColor=colors.HexColor("#FFF4E5"),
        textColor=AMBER,
        spaceAfter=9,
    )

    document = SimpleDocTemplate(
        str(output),
        pagesize=letter,
        rightMargin=0.62 * inch,
        leftMargin=0.62 * inch,
        topMargin=0.52 * inch,
        bottomMargin=0.60 * inch,
        title="SatoshiFlow Organizer-Compatible Backtest Report",
        author="SatoshiFlow",
    )
    story = [
        Spacer(1, 0.12 * inch),
        Paragraph("SATOSHIFLOW", title),
        Paragraph("Organizer-compatible BTC/USD strategy submission", subtitle),
        Paragraph("1. Objective and supplied dataset", heading),
        Paragraph(
            "The objective is a deterministic long/short BTC/USD trend strategy "
            "implemented through the challenge's original <b>BackTester</b> "
            "interface. The supplied repository dataset covers 2018-2022. The "
            "strategy is generic and is designed to run unchanged on "
            "evaluator-provided OHLCV data.",
            body,
        ),
        Paragraph(
            f"The run used <b>{official['dataset_filename']}</b> "
            f"({official['dataset_row_count']:,} daily rows), spanning "
            f"{official['dataset_first_date'][:10]} through "
            f"{official['dataset_last_date'][:10]}. SHA-256: "
            f"<font name='Courier'>{official['dataset_sha256']}</font>.",
            body,
        ),
        Paragraph("2. Official organizer-framework results", heading),
        official_metrics_table(official, body),
        Spacer(1, 5),
        Paragraph(
            "These headline values come only from the unmodified organizer "
            "framework after calling <b>bt.get_trades(1000)</b> and "
            "<b>bt.get_statistics()</b>. They are not mixed with the independent "
            "research engine.",
            note,
        ),
        Paragraph("3. Fixed strategy", heading),
        Paragraph(
            "The fixed parameters are Donchian 30, ADX 14 with threshold 20, "
            "EMA 200, ATR 14, and a 2.5 x ATR stop. A long requires close above "
            "the prior Donchian high and EMA, ADX >= 20, and DI+ > DI-. A short "
            "uses the symmetric conditions. The high/low-based trailing stop "
            "tracks the most favorable high for a long or low for a short. An "
            "opposite confirmed breakout may reverse the position.",
            body,
        ),
        PageBreak(),
        Paragraph("4. Indicator formulas", heading),
        Paragraph(
            "<b>TR</b> = max(H-L, |H-Cprev|, |L-Cprev|). "
            "<b>ATR</b> is Wilder's recursive average of TR. "
            "<b>+DM/-DM</b> retain the larger positive directional high/low "
            "move. <b>DI</b> = 100 x Wilder(DM) / ATR. "
            "<b>DX</b> = 100 x |DI+ - DI-| / (DI+ + DI-), and <b>ADX</b> is "
            "Wilder-smoothed DX. <b>EMA</b> = alpha x close + (1-alpha) x "
            "prior EMA, alpha = 2/(period+1). Donchian thresholds are "
            "high.shift(1).rolling(30).max() and "
            "low.shift(1).rolling(30).min().",
            body,
        ),
        Paragraph("5. Timing and signal convention", heading),
        Paragraph(
            "The organizer executes a signal at the signal row's close. To "
            "prevent same-row bias, the strategy forms a decision only after "
            "completed candle t and writes its executable signal to candle "
            "t+1. Thus decision t executes at t+1 close. Signal values follow "
            "the exact state convention: 0 hold, +/-1 open or close, and +/-2 "
            "reverse. A separate mechanical penultimate-row decision closes "
            "any open position on the final row; an unexecutable last-row "
            "economic decision is discarded.",
            body,
        ),
        Paragraph("6. Brokerage and accounting", heading),
        Paragraph(
            "Initial capital is exactly $1,000 and the configured brokerage is "
            "0.15%. The unchanged organizer <b>TradePair.pnl()</b> deducts "
            "0.15% of absolute trade quantity once per completed trade. That "
            "framework behavior is reported without alteration. The secondary "
            "research engine is deliberately stricter: it charges 0.15% on "
            "entry notional and again on exit notional and marks open positions "
            "to market daily.",
            body,
        ),
        Paragraph("7. Organizer equity path", heading),
        Image(
            str(organizer_results / "equity_curve.png"),
            width=6.95 * inch,
            height=3.77 * inch,
        ),
        Paragraph(
            "Figure 1. Organizer capital series with BTC close shown for context.",
            small,
        ),
        PageBreak(),
        Paragraph("8. Integrity checks", heading),
        Paragraph(
            "<b>LOOKAHEAD CHECK: PASS.</b> Indicators and economic decisions "
            "match full-data history at five cutoffs. "
            "<b>SIGNAL SHIFT CHECK: PASS.</b> Every executable signal equals "
            "the prior row's decision. <b>SIGNAL VALIDITY: PASS.</b> A replay "
            "accepts every transition under organizer rules. "
            "<b>REPRODUCIBILITY CHECK: PASS.</b> Two complete organizer runs "
            "produce identical signals, trades, statistics, and capital.",
            body,
        ),
        Paragraph("9. Independent robustness check", heading),
        Paragraph(
            "The same fixed decisions were also evaluated with an independent "
            "next-open, daily mark-to-market simulator using two-sided fees. "
            "These values are secondary diagnostics and are intentionally "
            "separate from the organizer headline metrics.",
            body,
        ),
        research_metrics_table(research, body),
        Spacer(1, 5),
        Image(
            str(research_results / "drawdown.png"),
            width=6.95 * inch,
            height=2.42 * inch,
        ),
        Paragraph(
            "Figure 2. Independent simulator daily mark-to-market drawdown.",
            small,
        ),
        Paragraph("10. Limitations", heading),
        Paragraph(
            "The supplied data ends in 2022 and may differ from evaluator data "
            "in exchange, timezone, or candle construction. The organizer "
            "framework executes at next-bar close after signal shifting and "
            "uses its own one-deduction fee model; the robustness engine shows "
            "the sensitivity to next-open execution and two-sided fees. Neither "
            "engine models spread, slippage, funding, borrow constraints, "
            "latency, or market impact. Historical results do not guarantee "
            "live performance.",
            body,
        ),
        Paragraph(
            "Source of truth: results/organizer/metrics.json. Every displayed "
            "headline value is loaded programmatically from that file.",
            small,
        ),
    ]
    document.build(story, onFirstPage=footer, onLaterPages=footer)


def build_markdown(official: dict, research: dict) -> str:
    return f"""# SatoshiFlow organizer-compatible report

## Dataset

- File: `{official['dataset_filename']}`
- Range: {official['dataset_first_date'][:10]} to {official['dataset_last_date'][:10]}
- SHA-256: `{official['dataset_sha256']}`

The supplied repository dataset covers 2018-2022. The strategy is generic and
is designed to run unchanged on evaluator-provided OHLCV data.

## Official organizer-framework metrics

| Metric | Value |
|---|---:|
| Final capital | {money(official['final_capital'])} |
| Net return | {100 * official['net_return']:.4f}% |
| Sharpe ratio | {official['sharpe_ratio']:.6f} |
| Maximum drawdown | {official['maximum_drawdown_percentage']:.4f}% |
| Win rate | {official['win_rate_percentage']:.4f}% |
| Total trades | {official['total_trades']} |
| Benchmark return | {official['benchmark_return_percentage']:.4f}% |

Decision on completed candle `t` is shifted to candle `t+1`, where the
unchanged organizer backtester executes it at the close.

## Independent robustness check

The separate next-open mark-to-market engine produced final equity
{money(research['final_equity'])}, Sharpe {research['sharpe_ratio']:.6f}, and
maximum drawdown {100 * research['max_drawdown']:.4f}%. These are secondary,
stricter diagnostics, not official headline results.

## Integrity

- LOOKAHEAD CHECK: PASS
- SIGNAL SHIFT CHECK: PASS
- SIGNAL VALIDITY CHECK: PASS
- ORGANIZER BACKTESTER CHECK: PASS
- REPRODUCIBILITY CHECK: PASS

The PDF and this file are generated from `results/organizer/metrics.json` and
the clearly separated `results/research/metrics.json`.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--organizer-results", default="results/organizer")
    parser.add_argument("--research-results", default="results/research")
    parser.add_argument("--output", default="SatoshiFlow_Report.pdf")
    parser.add_argument("--submission-dir", default="../SUBMIT_THESE")
    args = parser.parse_args()

    project_dir = Path(__file__).resolve().parent
    organizer_results = (project_dir / args.organizer_results).resolve()
    research_results = (project_dir / args.research_results).resolve()
    official = json.loads(
        (organizer_results / "metrics.json").read_text(encoding="utf-8")
    )
    research = json.loads(
        (research_results / "metrics.json").read_text(encoding="utf-8")
    )
    required_checks = (
        official["lookahead_check"],
        official["signal_shift_check"],
        official["signal_validity_check"],
        official["organizer_backtester_check"],
        official["reproducibility_check"],
        research["lookahead_check"],
        research["next_bar_execution_check"],
        research["reproducibility_check"],
    )
    if not all(required_checks):
        raise RuntimeError("refusing to report failed integrity checks")

    output = (project_dir / args.output).resolve()
    build_pdf(
        official,
        research,
        organizer_results,
        research_results,
        output,
    )
    (project_dir / "report.md").write_text(
        build_markdown(official, research), encoding="utf-8"
    )

    submission = (project_dir / args.submission_dir).resolve()
    submission.mkdir(parents=True, exist_ok=True)
    for child in submission.iterdir():
        if child.is_file():
            child.unlink()
    shutil.copy2(project_dir / "main.py", submission / "main.py")
    shutil.copy2(output, submission / output.name)
    expected = ["SatoshiFlow_Report.pdf", "main.py"]
    actual = sorted(child.name for child in submission.iterdir())
    if actual != expected:
        raise RuntimeError(f"unexpected submission contents: {actual}")
    print(f"Report: {output}")
    print(f"Submission: {submission}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

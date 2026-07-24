#!/usr/bin/env python3
"""Generate the report and submission package from verified JSON metrics."""

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
WARNING = colors.HexColor("#FFF4E5")
RED = colors.HexColor("#B42318")


def pct(value: float) -> str:
    return f"{100.0 * value:.2f}%"


def money(value: float) -> str:
    return f"${value:,.2f}"


def footer(canvas, document) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D0D5DD"))
    canvas.line(0.62 * inch, 0.45 * inch, 7.88 * inch, 0.45 * inch)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(0.62 * inch, 0.27 * inch, "SatoshiFlow | Verified backtest")
    canvas.drawRightString(
        7.88 * inch, 0.27 * inch, f"Page {document.page}"
    )
    canvas.restoreState()


def metrics_table(metrics: dict, body: ParagraphStyle) -> Table:
    rows = [
        ["Metric", "Verified value"],
        ["Evaluation period", metrics["evaluation_label"]],
        ["Initial / final equity", f"{money(metrics['initial_capital'])} / {money(metrics['final_equity'])}"],
        ["Net return", pct(metrics["net_return"])],
        ["Sharpe ratio", f"{metrics['sharpe_ratio']:.3f}"],
        ["Maximum drawdown", pct(metrics["max_drawdown"])],
        ["Win rate", f"{metrics['win_rate']:.2f}%"],
        ["Completed trades", str(metrics["total_trades"])],
        ["Total brokerage", money(metrics["total_brokerage"])],
        ["Buy-and-hold return", pct(metrics["buy_and_hold_return"])],
    ]
    table_rows = [
        rows[0],
        *[[Paragraph(str(cell), body) for cell in row] for row in rows[1:]],
    ]
    table = Table(
        table_rows,
        colWidths=[2.5 * inch, 4.35 * inch],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D0D5DD")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def build_pdf(metrics: dict, results_dir: Path, output: Path) -> None:
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.4,
        leading=12.2,
        textColor=NAVY,
        spaceAfter=6,
    )
    title = ParagraphStyle(
        "Title",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=27,
        leading=31,
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
        spaceAfter=18,
    )
    heading = ParagraphStyle(
        "Heading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=17,
        textColor=BLUE,
        spaceBefore=7,
        spaceAfter=6,
    )
    small = ParagraphStyle(
        "Small", parent=body, fontSize=8.2, leading=10.5, textColor=MUTED
    )
    callout = ParagraphStyle(
        "Callout",
        parent=body,
        borderColor=colors.HexColor("#F79009"),
        borderWidth=0.7,
        borderPadding=8,
        backColor=WARNING,
        textColor=RED,
        spaceAfter=12,
    )

    document = SimpleDocTemplate(
        str(output),
        pagesize=letter,
        rightMargin=0.62 * inch,
        leftMargin=0.62 * inch,
        topMargin=0.56 * inch,
        bottomMargin=0.60 * inch,
        title="SatoshiFlow Verified Backtest Report",
        author="SatoshiFlow",
    )
    story = [
        Spacer(1, 0.18 * inch),
        Paragraph("SATOSHIFLOW", title),
        Paragraph("Bias-free BTC/USD strategy backtest", subtitle),
    ]
    if metrics["provisional"]:
        story.append(
            Paragraph(
                "<b>PROVISIONAL DATASET:</b> The official 2019-2023 challenge "
                "file is absent. This report evaluates the repository's "
                "2018-2022 fallback data and does not claim official results.",
                callout,
            )
        )
    story.extend(
        [
            Paragraph("1. Objective and dataset", heading),
            Paragraph(
                "The objective is a reproducible BTC/USD trend strategy with "
                "strict next-candle execution, 0.15% brokerage on every entry "
                "and exit transaction, and daily mark-to-market accounting. "
                f"The selected file is <b>{metrics['dataset_filename']}</b> "
                f"({metrics['dataset_row_count']:,} rows), spanning "
                f"{metrics['dataset_first_date'][:10]} through "
                f"{metrics['dataset_last_date'][:10]}. Its SHA-256 is "
                f"<font name='Courier'>{metrics['dataset_sha256']}</font>.",
                body,
            ),
            Paragraph("2. Final out-of-sample metrics", heading),
            metrics_table(metrics, body),
            Spacer(1, 5),
            Paragraph(
                "Gross profit before brokerage was "
                f"<b>{money(metrics['gross_profit'])}</b>; net profit after "
                f"<b>{money(metrics['total_brokerage'])}</b> brokerage was "
                f"<b>{money(metrics['net_profit'])}</b>. There were "
                f"{metrics['entries']} entries, {metrics['exits']} exits, and "
                f"{metrics['reversals']} reversals.",
                body,
            ),
            PageBreak(),
            Paragraph("3. Strategy and formulas", heading),
            Paragraph(
                "The fixed strategy enters a 30-day Donchian breakout only "
                "when ADX is at least 20, directional movement agrees with the "
                "breakout, and close is on the correct side of the 200-day EMA. "
                "A 2.5 x ATR trailing stop exits the position; an opposite "
                "confirmed breakout may reverse it. Parameters were selected "
                "from a 16-combination grid using only 2019-2021 yearly results, "
                "ranked by median then worst-year Sharpe. The 2022 fallback "
                "test was excluded from selection.",
                body,
            ),
            Paragraph(
                "<b>True Range:</b> max(H-L, |H-Cprev|, |L-Cprev|). "
                "<b>ATR:</b> Wilder recursive average of True Range. "
                "<b>+DM/-DM:</b> the larger positive directional high/low move; "
                "<b>DI:</b> 100 x Wilder(DM) / ATR. "
                "<b>DX:</b> 100 x |DI+ - DI-| / (DI+ + DI-); "
                "<b>ADX:</b> Wilder average of DX. "
                "<b>EMA:</b> alpha x close + (1-alpha) x prior EMA, where "
                "alpha = 2/(period+1). Donchian levels use shifted prior highs "
                "and lows, so the breakout candle is excluded.",
                body,
            ),
            Paragraph("4. Timing, fees, and accounting", heading),
            Paragraph(
                "A decision is formed only after candle t is complete and is "
                "queued for execution at candle t+1 open. Entry notional fully "
                "deploys available equity after reserving the entry fee. The "
                "engine charges 0.15% on entry notional and 0.15% on exit "
                "notional. Reversals close the old trade and open the new one, "
                "charging both transactions. Any final open position is "
                "force-closed at the last close.",
                body,
            ),
            Paragraph(
                "Daily equity equals cash plus signed BTC quantity times daily "
                "close. Daily returns are equity(t)/equity(t-1)-1. Sharpe is "
                "sqrt(365) times mean daily return divided by sample standard "
                "deviation. Drawdown is equity/running maximum-1; the report "
                "states its largest magnitude as a positive percentage. Win "
                "rate uses completed trades only.",
                body,
            ),
            Paragraph("5. Mark-to-market equity", heading),
            Image(
                str(results_dir / "equity_curve.png"),
                width=6.95 * inch,
                height=3.82 * inch,
            ),
            Paragraph(
                "Figure 1. Daily equity after unrealized P&L and transaction fees.",
                small,
            ),
            PageBreak(),
            Paragraph("6. Drawdown and robustness", heading),
            Image(
                str(results_dir / "drawdown.png"),
                width=6.95 * inch,
                height=3.20 * inch,
            ),
            Paragraph(
                "Figure 2. Peak-to-trough drawdown from daily mark-to-market equity.",
                small,
            ),
            Paragraph("7. Integrity checks", heading),
            Paragraph(
                "<b>LOOKAHEAD CHECK: PASS.</b> Signals and every used indicator "
                "are invariant when future suffixes are appended. Checks compare "
                "all bars through several cutoffs, not only trade bars.",
                body,
            ),
            Paragraph(
                "<b>NEXT-BAR EXECUTION: PASS.</b> A fixture proves a target "
                "formed on t enters at t+1 open. "
                "<b>REPRODUCIBILITY CHECK: PASS.</b> Two complete runs produce "
                "identical signals, trades, equity, final equity, Sharpe, "
                "drawdown, and win rate.",
                body,
            ),
            Paragraph("8. Limitations", heading),
            Paragraph(
                "The official BTC_2019_2023_1d.csv training file is missing, so "
                "2023 cannot be evaluated and all results are provisional. The "
                "fallback file may differ in exchange, timezone, price source, "
                "or candle construction. The simulator includes brokerage but "
                "not bid-ask spread, slippage, funding, borrow constraints, "
                "latency, or market impact. Six trades are too few to infer "
                "stable live performance. Re-run the documented command with "
                "the official file before final external submission.",
                body,
            ),
            Spacer(1, 8),
            Paragraph(
                "Source of truth: results/metrics.json generated by main.py. "
                "Report values are loaded programmatically from that file.",
                small,
            ),
        ]
    )
    document.build(story, onFirstPage=footer, onLaterPages=footer)


def build_markdown(metrics: dict) -> str:
    return f"""# SatoshiFlow verified report

> **PROVISIONAL:** The official `BTC_2019_2023_1d.csv` file is missing.

## Dataset

- File: `{metrics['dataset_filename']}`
- Range: {metrics['dataset_first_date'][:10]} to {metrics['dataset_last_date'][:10]}
- SHA-256: `{metrics['dataset_sha256']}`
- Evaluation: {metrics['evaluation_label']}

## Strategy

30-day shifted Donchian breakout, ADX >= 20, DI direction confirmation,
200-day EMA regime filter, and 2.5 x ATR trailing stop. Decisions formed on
bar t execute at bar t+1 open.

## Verified metrics

| Metric | Value |
|---|---:|
| Final equity | {money(metrics['final_equity'])} |
| Net return | {pct(metrics['net_return'])} |
| Sharpe ratio | {metrics['sharpe_ratio']:.6f} |
| Maximum drawdown | {pct(metrics['max_drawdown'])} |
| Win rate | {metrics['win_rate']:.4f}% |
| Total trades | {metrics['total_trades']} |
| Total brokerage | {money(metrics['total_brokerage'])} |
| Buy-and-hold return | {pct(metrics['buy_and_hold_return'])} |

## Integrity

- LOOKAHEAD CHECK: PASS
- NEXT-BAR EXECUTION CHECK: PASS
- REPRODUCIBILITY CHECK: PASS

The PDF and this file are generated from `results/metrics.json`.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--output", default="SatoshiFlow_Report.pdf")
    parser.add_argument("--submission-dir", default="../SUBMIT_THESE")
    args = parser.parse_args()

    project_dir = Path(__file__).resolve().parent
    results_dir = (project_dir / args.results_dir).resolve()
    metrics = json.loads((results_dir / "metrics.json").read_text(encoding="utf-8"))
    required_checks = (
        metrics["lookahead_check"],
        metrics["next_bar_execution_check"],
        metrics["reproducibility_check"],
    )
    if not all(required_checks):
        raise RuntimeError("refusing to generate a report with failed integrity checks")

    output = (project_dir / args.output).resolve()
    build_pdf(metrics, results_dir, output)
    (project_dir / "report.md").write_text(
        build_markdown(metrics), encoding="utf-8"
    )

    submission = (project_dir / args.submission_dir).resolve()
    submission.mkdir(parents=True, exist_ok=True)
    for child in submission.iterdir():
        if child.is_file():
            child.unlink()
    shutil.copy2(project_dir / "main.py", submission / "main.py")
    shutil.copy2(output, submission / output.name)
    print(f"Report: {output}")
    print(f"Submission: {submission}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

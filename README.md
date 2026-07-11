# 📈 Quantitative Trading & AI/ML Learning Project

Welcome to the Quantitative Trading & AI/ML learning repository. This project is designed to help you transition from theory to practice by building and backtesting algorithmic trading strategies.

## 📂 Repository Structure

- [LEARNING_GUIDE.md](LEARNING_GUIDE.md) — A comprehensive guide detailing Quantitative Trading concepts (Long vs. Short, Sharpe Ratio, Drawdown, Lookahead Bias) and explaining the built-in strategy.
- [Basic Project/](file:///d:/Quant/Basic%20Project) — The core Python codebase and datasets:
  - [main.py](file:///d:/Quant/Basic%20Project/main.py) — The main script where strategy logic (e.g. Volume Spikes, Trailing Stop-Loss, Reversals) is applied.
  - [backtester.py](file:///d:/Quant/Basic%20Project/backtester.py) — The backtesting engine that simulates trading, handles transaction fees, and tracks performance metrics.
  - **`btc_18_22_1d.csv`** & **`final_data.csv`** — Historical Bitcoin data and generated signals.
  - **`Problem_statement.pdf`** — The original challenge instructions.

## 🚀 Getting Started

1. Read the [LEARNING_GUIDE.md](LEARNING_GUIDE.md) to understand the strategy logic and terminology.
2. Navigate to the `Basic Project` directory:
   ```bash
   cd "Basic Project"
   ```
3. Run the strategy and backtester:
   ```bash
   python main.py
   ```

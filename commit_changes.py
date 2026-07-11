#!/usr/bin/env python3
import subprocess
import os

def run_command(cmd, cwd=None):
    """Run a command and return the result."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    return result.returncode, result.stdout, result.stderr

# Navigate to Basic Project directory
os.chdir("d:/Quant/Basic Project")

# Check git status
code, stdout, stderr = run_command("git status")
print("Git Status:")
print(stdout)

# Add all files
code, stdout, stderr = run_command("git add -A")
print("\nGit Add Result:")
print("Return code:", code)
if stdout:
    print("Stdout:", stdout)
if stderr:
    print("Stderr:", stderr)

# Commit changes
commit_msg = """feat: implement complete BTC trading strategy backtesting system

- Add comprehensive technical indicators (ADX, DI+, DI-, ATR, EMA, Donchian, RSI, Bollinger Bands)
- Implement Hypothesis A: regime-filtered trend following with ADX threshold
- Add walk-forward validation framework for parameter optimization
- Create equity curve and performance metrics plotting
- Include no-lookahead bias validation
- Support multiple ADX threshold optimization (20, 25, 30)
- Add comprehensive testing and analysis scripts

Key features:
- Custom ATR calculation without external dependencies
- Donchian breakout entry signals
- ATR trailing stop exits
- Regime filtering to avoid choppy markets
- Year-based fold tagging for validation
- Performance visualization with matplotlib

Files modified:
- main.py: Updated with indicators, strategy, and analysis
- plot_equity.py: New equity curve plotting script
- walk_forward_validation.py: New parameter optimization script
- run_analysis.py: New comprehensive analysis script
- test_strategy.py: New test suite
"""

code, stdout, stderr = run_command(f'git commit -m "{commit_msg}"')
print("\nGit Commit Result:")
print("Return code:", code)
if stdout:
    print("Stdout:", stdout)
if stderr:
    print("Stderr:", stderr)

# Push to remote
code, stdout, stderr = run_command("git push origin main")
print("\nGit Push Result:")
print("Return code:", code)
if stdout:
    print("Stdout:", stdout)
if stderr:
    print("Stderr:", stderr)
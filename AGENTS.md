# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Commands

```bash
# Run the full pipeline (data processing -> stress test -> backtest)
python run_all.py

# Run individual modules
python data_processor.py    # EWMA volatility + VaR, outputs processed_data.parquet
python stress_test.py       # N-day VaR, manual override, price shock scenarios
python backtest.py          # Breakthrough counting, plots, backtest_results.xlsx
```

## Architecture

Three-stage pipeline for calculating margin requirements on Wind Futures Index data for gold (Au) and silver (Ag):

**data_processor.py** — Loads `AUFI_WI.parquet` and `AGFI_WI.parquet` (Wind futures index with OHLCV columns). Uses `close` price to compute log returns, then applies EWMA volatility with λ=0.98 (k=228 from tolerance=0.01). Calculates VaR at 99%, 99.7%, 99.99% confidence under a normal log-return assumption: `VaR = exp(z_{α/2} · σ) - 1`. Uses two-tailed z-scores (more conservative than one-tailed). Saves combined output to `processed_data.parquet`. All modules have input validation (file existence, required columns, minimum row count).

**stress_test.py** — Takes processed DataFrames from data_processor. Part 1: N-day forward VaR scaling volatility by √N for horizons [1, 1.8, 2, 2.8]. Part 2: manual volatility override (Au 2%, Ag 4%). Part 3: price shock scenarios — post-shock variance is `λ·σ² + (1-λ)·ln(1+z)²` for z ∈ [2%, 4%, 8%, 10%, 12%, 15%], then projects N-day VaR from the shocked variance. Returns a dict with keys 'part1', 'part2', 'part3'.

**backtest.py** — Two methods. Method 1: counts days where |return| exceeds both 99% VaR and a minimum threshold (Au 2%, Ag 4%), with 250-day rolling window. Method 2: scales std_log by √1.8 before recalculating VaR, then counts breakthroughs. Generates output_Au.png and output_Ag.png (per-metal charts with |Return| vs 99% and 99.99% VaR) and exports backtest_results.xlsx.

**run_all.py** — Orchestrates the three modules in sequence with hardcoded parameters (DECAY_FACTOR=0.98, TOLERANCE_LEVEL=0.01). Has top-level error handling with clear exit codes.

## Naming Conventions

- `z_scores` — normal distribution critical values (two-tailed z_{α/2})
- `manual_vol_*` — manually specified volatility (not returns)
- `shock_pcts`, `log_shock_factors` — price shock scenario parameters
- `horizons` — N-day forward periods

## Data

Input parquet files contain Wind Commodity Futures Index daily data with columns: `date`, `open`, `high`, `low`, `close`, `settle`, `volume`, `oi`, `amt`. Au data starts 2008-01-09 (~4477 rows), Ag data starts 2012-05-10 (~3425 rows). Generated output files (`processed_data.parquet`, `*.png`, `*.xlsx`) are ignored by git and recreated locally by the pipeline. The model uses only the `close` column for pricing.

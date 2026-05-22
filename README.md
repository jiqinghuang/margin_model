# Margin Model — Gold & Silver Wind Futures Index

A three-stage pipeline for calculating margin requirements on Wind Futures Index data for gold (Au) and silver (Ag), based on EWMA volatility and VaR methodology.

## Architecture

```
AUFI_WI.parquet ──┐
                  ├──> data_processor.py ──> processed_data.parquet ──┬──> stress_test.py
AGFI_WI.parquet ──┘                                                   └──> backtest.py ──> output_*.png
                                                                                       backtest_results.xlsx
```

### Stage 1: Data Processing (`data_processor.py`)

- Loads Wind futures index parquet files (OHLCV format)
- Computes log returns from closing prices
- Applies EWMA volatility with λ=0.98 (RiskMetrics-style decay)
- Calculates VaR at 99%, 99.7%, 99.99% confidence under a lognormal assumption
- Outputs `processed_data.parquet`

### Stage 2: Stress Testing (`stress_test.py`)

Three-part analysis:
1. **N-day Forward VaR** — scales EWMA volatility by √N for horizons [1, 1.8, 2, 2.8]
2. **Manual Volatility Override** — VaR under fixed volatilities (Au 2%, Ag 4%)
3. **Price Shock Scenarios** — post-shock variance via λ·σ² + (1−λ)·ln(1+z)² for shocks of 2%–15%

### Stage 3: Backtesting (`backtest.py`)

- **Method 1** — counts days where |return| exceeds 99% VaR with minimum return threshold (Au 2%, Ag 4%), 250-day rolling window
- **Method 2** — scales volatility by √1.8 before recalculating VaR, then counts breakthroughs
- Generates per-metal PNG charts (|Return| vs 99% and 99.99% VaR)
- Exports `backtest_results.xlsx`

## Quick Start

```bash
pip install numpy pandas scipy matplotlib openpyxl
python run_all.py
```

## Output

| File | Description |
|------|-------------|
| `processed_data.parquet` | Processed data with returns, volatility, VaR columns |
| `output_Au.png` | Au backtest chart |
| `output_Ag.png` | Ag backtest chart |
| `backtest_results.xlsx` | Backtest results (both methods) |

## Data

Wind Commodity Futures Index daily data with columns: `date`, `open`, `high`, `low`, `close`, `settle`, `volume`, `oi`, `amt`. Uses `close` for pricing.

- Au: 2008-01-09 ~ present (~4,460 rows)
- Ag: 2012-05-10 ~ present (~3,400 rows)

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `DECAY_FACTOR` | 0.98 | EWMA decay factor λ |
| `TOLERANCE_LEVEL` | 0.01 | EWMA initialization window tolerance (yields k=228) |
| `ALPHA_LIST` | [0.01, 0.003, 0.0001] | VaR confidence levels (99%, 99.7%, 99.99%) |

## Methodology Notes

- **Two-tailed VaR**: uses z_{α/2} rather than one-tailed z_α, producing more conservative margin estimates (at 99%: z=2.576 vs z=2.326)
- **Lognormal VaR**: VaR = exp(z · σ) − 1, assuming log returns ~ N(0, σ²)
- **EWMA**: initialization window k=228, recurrence v_{t+1} = λ·v_t + (1−λ)·r_t²

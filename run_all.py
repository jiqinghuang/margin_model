"""
Margin Model - Main Entry Point
================================
Orchestrates the three-stage pipeline:
  1. Data processing (EWMA volatility + VaR)
  2. Stress testing (N-day forward VaR, manual override, price shock scenarios)
  3. Backtesting (breakthrough counting, plots, Excel export)

Output:
  - processed_data.parquet
  - output_Au.png / output_Ag.png
  - backtest_results.xlsx
"""

from pathlib import Path
import sys

_BASE_DIR = Path(__file__).resolve().parent

DECAY_FACTOR = 0.98
TOLERANCE_LEVEL = 0.01


def main():
    alpha_list = [0.01, 0.003, 0.0001]  # 99%, 99.7%, 99.99% VaR

    print('=' * 70)
    print('  Margin Model - Au (Gold) & Ag (Silver) Wind Futures Index')
    print('=' * 70)
    print(f'\nParameters: decay_factor={DECAY_FACTOR}, tolerance={TOLERANCE_LEVEL}')
    print(f'VaR levels: {[(1 - a) * 100 for a in alpha_list]}\n')

    print('>>> Step 1/3: Data Processing (EWMA volatility + VaR)')
    print('-' * 55)
    from data_processor import run_data_processor
    df_au, df_ag = run_data_processor(
        decay_factor=DECAY_FACTOR,
        tolerance_level=TOLERANCE_LEVEL,
        output_path=str(_BASE_DIR / 'processed_data.parquet')
    )

    print('\n>>> Step 2/3: Stress Testing')
    print('-' * 55)
    from stress_test import run_stress_test
    run_stress_test(df_au, df_ag, decay_factor=DECAY_FACTOR)

    print('\n>>> Step 3/3: Backtesting')
    print('-' * 55)
    from backtest import run_backtest
    run_backtest(df_au, df_ag)

    print('\n' + '=' * 70)
    print('  Margin Model - All steps completed.')
    print('  Output files:')
    print('    - processed_data.parquet')
    print('    - output_Au.png')
    print('    - output_Ag.png')
    print('    - backtest_results.xlsx')
    print('=' * 70)


if __name__ == '__main__':
    try:
        main()
    except (FileNotFoundError, ValueError) as e:
        print(f'\nERROR: {e}', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f'\nUNEXPECTED ERROR: {e}', file=sys.stderr)
        sys.exit(1)

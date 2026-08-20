import os
from pathlib import Path
import numpy as np
import pandas as pd

_BASE_DIR = Path(__file__).resolve().parent
from scipy import stats
def load_parquet_data(filepath: str) -> pd.DataFrame:
    """Load Wind futures index parquet data, set date as index."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f'Data file not found: {filepath}')
    df = pd.read_parquet(filepath)
    if df.empty:
        raise ValueError(f'Data file is empty: {filepath}')
    required = {'date', 'close'}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f'Missing required columns {missing} in {filepath}')
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date').sort_index()
    return df


def _compute_ewma_variance(returns_log: pd.Series, decay_factor: float, k: int) -> pd.Series:
    """
    Compute EWMA variance series.

    v_k = (1-λ) * Σ λ^i * Ln(r_{k-i})²   (initialization)
    v_{k+1} = λ * v_k + (1-λ) * Ln(r_k)²  (recurrence)

    ewma_v[t] is the forecast for day t, using data up to day t-1.
    The series has one extra entry at the end (NaN) for next-day forecast.
    """
    n = len(returns_log)
    # Create series with one extra row for next-day forecast
    ewma_variance = pd.Series(index=returns_log.index, dtype=float)
    ewma_variance[returns_log.index[-1] + pd.Timedelta('1 days')] = np.nan

    # Precompute weights: from newest to oldest
    weights = decay_factor ** np.arange(k)[::-1]

    # Initialize: v_k
    init_variance = (1 - decay_factor) * np.sum(weights * (returns_log.iloc[0:k] ** 2))
    ewma_variance.iloc[k] = init_variance

    # Recurrence
    current_variance = init_variance
    for i in range(k, len(ewma_variance) - 1):
        current_variance = (1 - decay_factor) * (returns_log.iloc[i] ** 2) + decay_factor * current_variance
        ewma_variance.iloc[i + 1] = current_variance

    return ewma_variance


def process_data(filepath: str, metal_name: str, decay_factor: float, k: int,
                 alpha_list: np.ndarray) -> pd.DataFrame:
    """
    Full pipeline for one metal: load data, compute returns, EWMA volatility, VaR.

    Returns DataFrame with columns: close, r_{metal}, r_{metal}_log, std_log, VaR columns
    """
    df = load_parquet_data(filepath)
    if len(df) <= k:
        raise ValueError(
            f'{metal_name}: need > {k} rows for EWMA initialization (k={k}), got {len(df)}'
        )

    # Use close price
    price = df['close']

    # Returns and log returns
    returns = price.pct_change()
    returns_log = np.log1p(returns)

    returns = returns.dropna()
    returns_log = returns_log.dropna()
    returns.name = f'r_{metal_name}'
    returns_log.name = f'r_{metal_name}_log'

    # EWMA volatility
    ewma_variance = _compute_ewma_variance(returns_log, decay_factor, k)
    std_log = np.sqrt(ewma_variance)
    std_log.name = 'std_log'

    # Combine
    result = pd.concat([price, returns, returns_log, std_log], axis=1)

    # VaR under normal log-return assumption: VaR = exp(z · σ) − 1
    # Uses two-tailed z-scores (z_{α/2}), more conservative than one-tailed.
    # Example: at 99% confidence, z = 2.576 (two-tailed) vs z = 2.326 (one-tailed).
    var_names = [f'{round((1 - alpha) * 100, 4)}% VaR' for alpha in alpha_list]
    z_scores = stats.norm.ppf(1 - alpha_list / 2)
    for z_score, var_name in zip(z_scores, var_names):
        result[var_name] = np.exp(z_score * result['std_log']) - 1

    return result


def run_data_processor(decay_factor: float = 0.98, tolerance_level: float = 0.01,
                       output_path: str = 'processed_data.parquet'):
    """
    Main entry point: process Au and Ag data, save results.

    Parameters
    ----------
    decay_factor : float
        EWMA decay factor λ
    tolerance_level : float
        Tolerance for initializing EWMA
    output_path : str
        Path to save processed data (parquet format)
    """
    k = int(np.ceil(np.log(tolerance_level) / np.log(decay_factor)))
    alpha_list = np.array([0.01, 0.003, 0.0001])

    print(f'EWMA parameters: decay_factor={decay_factor}, tolerance={tolerance_level}, k={k}')
    print(f'VaR confidence levels: {[(1 - a) * 100 for a in alpha_list]}')

    def _latest_pct(df, metal):
        """Return tail-5 rows of key columns scaled to percentage."""
        cols = [f'r_{metal}', f'r_{metal}_log', 'std_log']
        cols += [c for c in df.columns if 'VaR' in c]
        return df[cols].tail(5) * 100

    # Process Au
    print('\n--- Processing Au (AUFI_WI.parquet) ---')
    df_au = process_data(str(_BASE_DIR / 'AUFI_WI.parquet'), 'Au', decay_factor, k, alpha_list)
    print(f'Au data: {df_au.shape[0]} rows, {df_au.index[0].date()} ~ {df_au.index[-1].date()}')
    print('Latest Au values (%):')
    print(_latest_pct(df_au, 'Au').to_string())

    # Process Ag
    print('\n--- Processing Ag (AGFI_WI.parquet) ---')
    df_ag = process_data(str(_BASE_DIR / 'AGFI_WI.parquet'), 'Ag', decay_factor, k, alpha_list)
    print(f'Ag data: {df_ag.shape[0]} rows, {df_ag.index[0].date()} ~ {df_ag.index[-1].date()}')
    print('Latest Ag values (%):')
    print(_latest_pct(df_ag, 'Ag').to_string())

    # Save
    result = {'Au': df_au, 'Ag': df_ag}
    combined = pd.concat([df_au.assign(metal='Au'), df_ag.assign(metal='Ag')])
    # resolve output_path relative to module dir if not absolute
    _out = Path(output_path)
    if not _out.is_absolute():
        _out = _BASE_DIR / _out
    combined.to_parquet(_out)
    print(f'\nProcessed data saved to {_out}')

    return df_au, df_ag


if __name__ == '__main__':
    df_au, df_ag = run_data_processor()

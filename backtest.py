from pathlib import Path
import numpy as np
import pandas as pd

_BASE_DIR = Path(__file__).resolve().parent
from scipy import stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Chinese font setup
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


def backtest_method1(df_au: pd.DataFrame, df_ag: pd.DataFrame,
                     au_threshold: float = 0.02, ag_threshold: float = 0.04) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Backtest Method 1: Count breakthroughs with minimum return threshold.

    A breakthrough occurs when abs(return) > VaR AND abs(return) >= threshold.
    250-day rolling sum of breakthroughs is computed.
    """
    print('=' * 70)
    print('BACKTEST METHOD 1: Breakthrough Count with Threshold')
    print(f'  Au threshold: {au_threshold*100}%  |  Ag threshold: {ag_threshold*100}%')
    print('=' * 70)

    results = {}

    for metal, df, threshold in [('Au', df_au.copy(), au_threshold),
                                   ('Ag', df_ag.copy(), ag_threshold)]:
        r_col = f'r_{metal}'
        df['abs_return'] = df[r_col].abs()
        df['breakthrough'] = (df['abs_return'] > df['99.0% VaR']) & (df['abs_return'] >= threshold)
        df['250d_breakthroughs'] = df['breakthrough'].rolling(window=250).sum()

        total_bt = df['breakthrough'].sum()
        total_days = df['breakthrough'].notna().sum()
        last_val = df['250d_breakthroughs'].iloc[-1]
        recent_bt = last_val if pd.notna(last_val) else np.nan

        print(f'\n{metal}:')
        print(f'  Total breakthroughs: {int(total_bt)} / {total_days} trading days')
        print(f'  Breakthrough rate: {total_bt/total_days*100:.2f}%')
        print(f'  250-day rolling breakthroughs (latest): {recent_bt:.0f}')

        results[metal] = df

    return results['Au'], results['Ag']


def backtest_method2(df_au: pd.DataFrame, df_ag: pd.DataFrame, eta: float = 1.8) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Backtest Method 2: Adjust std_log by factor eta, recalculate VaR.

    A multiplier eta is applied to the variance (so std is scaled by sqrt(eta)).
    This tests how VaR performs when volatility is intentionally scaled up.
    """
    print('\n' + '=' * 70)
    print(f'BACKTEST METHOD 2: Volatility Adjustment Factor eta = {eta}')
    print('=' * 70)

    alpha_list = np.array([0.01, 0.003, 0.0001])
    var_names = [f'{round((1 - alpha) * 100, 4)}% VaR' for alpha in alpha_list]

    results = {}
    for metal, df in [('Au', df_au.copy()), ('Ag', df_ag.copy())]:

        df[f'{eta}_std_log'] = np.sqrt(eta) * df['std_log']

        z_scores = stats.norm.ppf(1 - alpha_list / 2)
        for z_score, var_name in zip(z_scores, var_names):
            df[var_name] = np.exp(z_score * df[f'{eta}_std_log']) - 1

        r_col = f'r_{metal}'
        df['abs_return'] = df[r_col].abs()
        df['breakthrough'] = df['abs_return'] > df['99.0% VaR']
        df['250d_breakthroughs'] = df['breakthrough'].rolling(window=250).sum()

        total_bt = df['breakthrough'].sum()
        total_days = df['breakthrough'].notna().sum()
        last_val = df['250d_breakthroughs'].iloc[-1]
        recent_bt = last_val if pd.notna(last_val) else np.nan
        expected_bt = total_days * 0.01  # At 99% VaR, expect ~1% of days to break through

        print(f'\n{metal} (eta={eta}):')
        print(f'  Total breakthroughs: {int(total_bt)} / {total_days} trading days')
        print(f'  Breakthrough rate: {total_bt/total_days*100:.2f}%')
        print(f'  Expected breakthroughs at 99%: ~{expected_bt:.0f}')
        print(f'  250-day rolling breakthroughs (latest): {recent_bt:.0f}')

        results[metal] = df

    return results['Au'], results['Ag']


def plot_backtest(df_au: pd.DataFrame, df_ag: pd.DataFrame,
                  tail_days: int = 1250, save: bool = True) -> None:
    """Plot VaR vs absolute returns — one chart per metal, two VaR levels."""
    var_cols = ['99.0% VaR', '99.99% VaR']
    var_labels = ['99% VaR', '99.99% VaR']

    for df, metal in [(df_au, 'Au'), (df_ag, 'Ag')]:
        r_col = f'r_{metal}'
        cols = [r_col] + var_cols
        plot_df = df[cols].tail(tail_days).copy()
        plot_df['abs_return'] = plot_df[r_col].abs()
        plot_df = plot_df.dropna()

        fig, ax = plt.subplots(figsize=(20, 8))
        (100 * plot_df[['abs_return'] + var_cols]).plot(
            ax=ax, grid=True,
            title=f'{metal} — VaR vs Absolute Return (last {tail_days} days)'
        )
        ax.set_ylabel('%')
        ax.legend(['|Return|'] + var_labels)

        if save:
            filename = str(_BASE_DIR / f'output_{metal}.png')
            fig.savefig(filename, dpi=200, bbox_inches='tight')
            print(f'Plot saved: {filename}')

        plt.close(fig)


def export_backtest_results(df_au: pd.DataFrame, df_ag: pd.DataFrame,
                            filepath: str = 'backtest_results.xlsx') -> None:
    """Export backtest results to Excel."""
    _fp = Path(filepath)
    if not _fp.is_absolute():
        _fp = _BASE_DIR / _fp
    with pd.ExcelWriter(_fp) as writer:
        for df, sheet in [(df_au, 'Au'), (df_ag, 'Ag')]:
            out = df.copy()
            out['Year'] = out.index.year
            out.to_excel(writer, sheet_name=sheet)
    print(f'Backtest results exported to {_fp}')


def run_backtest(df_au: pd.DataFrame, df_ag: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run all backtesting methods and generate outputs."""
    # --- Input validation ---
    for name, df in [('Au', df_au), ('Ag', df_ag)]:
        if df.empty:
            raise ValueError(f'{name} DataFrame is empty')
        required = {f'r_{name}', 'std_log', '99.0% VaR'}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f'{name} DataFrame missing columns: {missing}')

    # Method 1
    df_au_m1, df_ag_m1 = backtest_method1(df_au, df_ag)

    # Method 2
    df_au_m2, df_ag_m2 = backtest_method2(df_au, df_ag)

    # Plots using Method 1 results
    plot_backtest(df_au_m1, df_ag_m1)

    # Export Method 2 results (with eta-adjusted VaR)
    export_backtest_results(df_au_m2, df_ag_m2)

    return df_au_m1, df_ag_m1, df_au_m2, df_ag_m2


if __name__ == '__main__':
    from data_processor import run_data_processor
    df_au, df_ag = run_data_processor()
    run_backtest(df_au, df_ag)

import numpy as np
import pandas as pd
from scipy import stats


def run_stress_test(df_au: pd.DataFrame, df_ag: pd.DataFrame,
                    decay_factor: float = 0.98):
    """
    Stress testing module: forward VaR, manual volatility, and price shock scenarios.

    Part 1: N-day forward VaR using current EWMA volatility forecast.
    Part 2: VaR with manually specified volatility (Au 2%, Ag 4%).
    Part 3: Price shock scenarios -- post-shock variance is
            lambda*sigma^2 + (1-lambda)*ln(1+z)^2 for shock magnitudes
            of 2%, 4%, 8%, 10%, 12%, and 15%.

    Returns
    -------
    dict with keys 'part1', 'part2', 'part3':
        part1: {'Au': DataFrame, 'Ag': DataFrame} -- N-day forward VaR
        part2: {'Au': DataFrame, 'Ag': DataFrame} -- manual volatility VaR
        part3: {'Au': {horizon: DataFrame}, 'Ag': {horizon: DataFrame}} -- shock scenarios
    """
    # --- Input validation ---
    for name, df in [('Au', df_au), ('Ag', df_ag)]:
        if df.empty:
            raise ValueError(f'{name} DataFrame is empty')
        if len(df) < 2:
            raise ValueError(f'{name} DataFrame needs at least 2 rows, got {len(df)}')
        for col in [f'r_{name}', f'r_{name}_log', 'std_log']:
            if col not in df.columns:
                raise ValueError(f'{name} DataFrame missing column: {col}')

    if df_au.index[-1] != df_ag.index[-1]:
        raise ValueError(
            f'Date mismatch: Au last date={df_au.index[-1].date()}, '
            f'Ag last date={df_ag.index[-1].date()}'
        )

    # --- Parameters ---
    alpha_list = np.array([0.01, 0.003, 0.0001])
    var_names = [f'{round((1 - alpha) * 100, 4)}% VaR' for alpha in alpha_list]
    # Two-tailed z-scores (same convention as data_processor)
    z_scores = stats.norm.ppf(1 - alpha_list / 2)
    horizons = np.array([1, 1.8, 2, 2.8])

    today_date = df_au.index[-1]
    yesterday_date = df_au.index[-2]

    print(f'Previous trading day: {yesterday_date.date()}')
    print(f'Current date (latest data): {today_date.date()}')
    print()

    au_r = df_au.loc[yesterday_date, 'r_Au'] * 100
    au_r_log = df_au.loc[yesterday_date, 'r_Au_log'] * 100
    au_std = df_au.loc[today_date, 'std_log'] * 100
    ag_r = df_ag.loc[yesterday_date, 'r_Ag'] * 100
    ag_r_log = df_ag.loc[yesterday_date, 'r_Ag_log'] * 100
    ag_std = df_ag.loc[today_date, 'std_log'] * 100

    print(f'Previous day Au return: {au_r:.3f}%')
    print(f'Previous day Au log return: {au_r_log:.3f}%')
    print(f'Forecast Au volatility (std_log) for {today_date.date()}: {au_std:.3f}%')
    print('-' * 50)
    print(f'Previous day Ag return: {ag_r:.3f}%')
    print(f'Previous day Ag log return: {ag_r_log:.3f}%')
    print(f'Forecast Ag volatility (std_log) for {today_date.date()}: {ag_std:.3f}%')
    print()

    # ========== Part 1: N-day Forward VaR ==========
    print('=' * 70)
    print('PART 1: N-day Forward VaR using EWMA volatility forecast')
    print('=' * 70)

    au_std_today = df_au.loc[today_date, 'std_log']
    ag_std_today = df_ag.loc[today_date, 'std_log']

    output_au = pd.DataFrame(columns=['std_log'] + var_names)
    output_ag = pd.DataFrame(columns=['std_log'] + var_names)

    for h in horizons:
        vol_au = np.sqrt(h) * au_std_today
        var_au = np.exp(z_scores * vol_au) - 1
        output_au.loc[f'{h} days'] = np.append(vol_au, var_au) * 100

        vol_ag = np.sqrt(h) * ag_std_today
        var_ag = np.exp(z_scores * vol_ag) - 1
        output_ag.loc[f'{h} days'] = np.append(vol_ag, var_ag) * 100

    print(f'\nAu -- based on forecast volatility {au_std:.3f}% on {today_date.date()}:')
    print(output_au.to_string())
    print(f'\nAg -- based on forecast volatility {ag_std:.3f}% on {today_date.date()}:')
    print(output_ag.to_string())

    # ========== Part 2: Manual Volatility Override ==========
    print('\n' + '=' * 70)
    print('PART 2: Manual Volatility Override (Stress Test)')
    print('=' * 70)

    manual_vol_au = 2 / 100
    manual_vol_ag = 4 / 100

    output_au_manual = pd.DataFrame(columns=['std_log'] + var_names)
    output_ag_manual = pd.DataFrame(columns=['std_log'] + var_names)

    for h in horizons:
        vol_au = np.sqrt(h) * manual_vol_au
        var_au = np.exp(z_scores * vol_au) - 1
        output_au_manual.loc[f'{h} days'] = np.append(vol_au, var_au) * 100

        vol_ag = np.sqrt(h) * manual_vol_ag
        var_ag = np.exp(z_scores * vol_ag) - 1
        output_ag_manual.loc[f'{h} days'] = np.append(vol_ag, var_ag) * 100

    print(f'\nAu -- manual volatility={manual_vol_au*100}%:')
    print(output_au_manual.to_string())
    print(f'\nAg -- manual volatility={manual_vol_ag*100}%:')
    print(output_ag_manual.to_string())

    # ========== Part 3: Price Shock Scenarios ==========
    print('\n' + '=' * 70)
    print('PART 3: Price Shock Scenarios')
    print('=' * 70)

    # Post-shock variance: λ·σ² + (1-λ)·ln(1+z)² for each shock magnitude
    shock_pcts = np.array([2, 4, 8, 10, 12, 15]) / 100
    log_shock_factors = np.log(1 + shock_pcts)
    shock_results = {}

    for metal, df, std_today in [('Au', df_au, au_std_today), ('Ag', df_ag, ag_std_today)]:
        print(f'\n--- {metal} ---')
        print(f'Forecast volatility on {today_date.date()}: {std_today*100:.3f}%')

        shocked_variances = decay_factor * std_today ** 2 + (1 - decay_factor) * log_shock_factors ** 2
        metal_shocks = {}

        for h in horizons:
            output = pd.DataFrame(columns=['std_log'] + var_names)
            for shock_pct, var in zip(shock_pcts, shocked_variances):
                vol = np.sqrt(h * var)
                var_vals = np.exp(z_scores * vol) - 1
                output.loc[f'{shock_pct*100}% shock'] = np.append(vol, var_vals) * 100
            metal_shocks[f'{h}_days'] = output
            print(f'\n  {h}-day horizon:')
            print(output.to_string())

        shock_results[metal] = metal_shocks

    return {
        'part1': {'Au': output_au, 'Ag': output_ag},
        'part2': {'Au': output_au_manual, 'Ag': output_ag_manual},
        'part3': shock_results,
    }


if __name__ == '__main__':
    from data_processor import run_data_processor
    df_au, df_ag = run_data_processor()
    run_stress_test(df_au, df_ag)

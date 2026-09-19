"""margin_model 单元测试。

用法：python -m unittest -v test_model
"""
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

import data_processor as dp
from backtest import backtest_method1
from data_processor import _compute_ewma_variance, process_data, resolve_data_path


def _make_returns(n=40, seed=11):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range('2026-01-01', periods=n)
    return pd.Series(rng.normal(0, 0.01, size=n), index=dates, name='r_log')


class EwmaTests(unittest.TestCase):
    LAMBDA = 0.94  # 故意不同于默认 0.98，防止参数被硬编码

    def test_matches_manual_recurrence(self):
        r = _make_returns()
        k = 5
        v = _compute_ewma_variance(r, self.LAMBDA, k)

        # 手工按文档公式重算：v_k = (1-λ)Σλ^i r_{k-i}²，之后逐日递推
        weights = self.LAMBDA ** np.arange(k)[::-1]
        expected = (1 - self.LAMBDA) * float(np.sum(weights * r.iloc[:k].to_numpy() ** 2))
        self.assertAlmostEqual(v.iloc[k], expected, places=15)
        for i in range(k, len(v) - 1):
            expected = self.LAMBDA * expected + (1 - self.LAMBDA) * float(r.iloc[i] ** 2)
            self.assertAlmostEqual(v.iloc[i + 1], expected, places=15)

    def test_no_lookahead_last_return_only_affects_forecast(self):
        r = _make_returns()
        r2 = r.copy()
        r2.iloc[-1] = 0.5  # 在最后一天制造巨大冲击
        v1 = _compute_ewma_variance(r, self.LAMBDA, 5)
        v2 = _compute_ewma_variance(r2, self.LAMBDA, 5)

        # 冲击只能影响"下一日预测"（末行），之前所有行的波动率必须不变
        np.testing.assert_allclose(v1.iloc[:-1], v2.iloc[:-1])
        self.assertNotAlmostEqual(v1.iloc[-1], v2.iloc[-1])

    def test_forecast_row_appended(self):
        r = _make_returns(n=25)
        v = _compute_ewma_variance(r, self.LAMBDA, 5)
        self.assertEqual(len(v), len(r) + 1)
        self.assertEqual(v.index[-1], r.index[-1] + pd.Timedelta('1 days'))
        self.assertTrue(np.isnan(v.iloc[-1]) is False or not np.isnan(v.iloc[-1]))


class VarTests(unittest.TestCase):
    def test_two_tailed_z_scores(self):
        alpha_list = np.array([0.01, 0.003, 0.0001])
        z = stats.norm.ppf(1 - alpha_list / 2)
        self.assertAlmostEqual(z[0], 2.5758293035489004, places=6)

    def test_invalid_ewma_params_rejected(self):
        with self.assertRaisesRegex(ValueError, 'decay_factor'):
            dp.run_data_processor(decay_factor=1.0)
        with self.assertRaisesRegex(ValueError, 'decay_factor'):
            dp.run_data_processor(decay_factor=0.0)
        with self.assertRaisesRegex(ValueError, 'tolerance_level'):
            dp.run_data_processor(tolerance_level=0.0)

    def test_process_data_end_to_end(self):
        rng = np.random.default_rng(3)
        n = 80
        close = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, size=n)))
        df = pd.DataFrame({
            'date': pd.bdate_range('2026-01-01', periods=n).strftime('%Y-%m-%d'),
            'close': close,
        })
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'XFI_WI.parquet'
            df.to_parquet(path)
            k = 5
            result = process_data(str(path), 'X', 0.98, k, np.array([0.01, 0.003, 0.0001]))

        # 输出比原始价格多一行（下一交易日预测行）
        self.assertEqual(len(result), n + 1)
        self.assertTrue(np.isnan(result['close'].iloc[-1]))
        self.assertFalse(np.isnan(result['std_log'].iloc[-1]))
        # VaR 列 = exp(z·σ) − 1，且与 std_log 的 NaN 模式一致（首个价格日 + k 行预热）
        self.assertEqual(int(result['std_log'].isna().sum()), k + 1)
        var99 = result['99.0% VaR']
        valid = var99.dropna()
        self.assertTrue((valid > 0).all())
        recomputed = np.exp(stats.norm.ppf(1 - 0.01 / 2) * result['std_log']) - 1
        np.testing.assert_allclose(var99.fillna(-1), recomputed.fillna(-1))


class DataPathTests(unittest.TestCase):
    def test_prefers_sibling_with_newer_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            local_dir = Path(tmp) / 'local'
            sib_dir = Path(tmp) / 'sibling'
            local_dir.mkdir()
            sib_dir.mkdir()
            base = pd.DataFrame({
                'date': pd.bdate_range('2026-01-05', periods=10).strftime('%Y-%m-%d'),
                'close': np.arange(10.0),
            })
            local_file = local_dir / 'XFI_WI.parquet'
            sib_file = sib_dir / 'XFI_WI.parquet'
            base.to_parquet(local_file)
            base.iloc[:-3].to_parquet(sib_file)  # 截止更早

            original_sibling = dp._SIBLING_DATA_DIR
            original_base = dp._BASE_DIR
            try:
                dp._SIBLING_DATA_DIR = sib_dir
                dp._BASE_DIR = local_dir
                # 本地更新 → 用本地
                self.assertEqual(resolve_data_path('XFI_WI.parquet'), local_file)
                # 平级截止日期严格更新 → 用平级
                newer = pd.concat([
                    base,
                    pd.DataFrame({
                        'date': pd.bdate_range('2026-01-20', periods=2).strftime('%Y-%m-%d'),
                        'close': [10.0, 11.0],
                    }),
                ])
                newer.to_parquet(sib_file)
                self.assertEqual(resolve_data_path('XFI_WI.parquet'), sib_file)
                # 平级更旧 → 仍用本地
                base.iloc[:-5].to_parquet(sib_file)
                self.assertEqual(resolve_data_path('XFI_WI.parquet'), local_file)
                # 平级缺文件 → 用本地
                sib_file.unlink()
                self.assertEqual(resolve_data_path('XFI_WI.parquet'), local_file)
                # 本地缺文件 → 用平级
                local_file.unlink()
                base.to_parquet(sib_file)
                self.assertEqual(resolve_data_path('XFI_WI.parquet'), sib_file)
            finally:
                dp._SIBLING_DATA_DIR = original_sibling
                dp._BASE_DIR = original_base


class BacktestInvariantTests(unittest.TestCase):
    def test_no_breakthrough_during_warmup(self):
        rng = np.random.default_rng(5)
        n = 300
        r = rng.normal(0, 0.005, size=n)
        warmup = 10
        std_log = np.full(n, 0.01)
        std_log[:warmup] = np.nan
        var = np.where(np.isnan(std_log), np.nan, 0.02)
        df_au = pd.DataFrame({
            'r_Au': r,
            'std_log': std_log,
            '99.0% VaR': var,
        }, index=pd.bdate_range('2025-01-01', periods=n))
        df_ag = df_au.rename(columns={'r_Au': 'r_Ag'})

        out_au, out_ag = backtest_method1(df_au.copy(), df_ag.copy(),
                                          au_threshold=0.04, ag_threshold=0.04)
        for out in (out_au, out_ag):
            # 预热期 VaR 为 NaN，构造上不允许出现突破
            self.assertFalse(out.loc[out['99.0% VaR'].isna(), 'breakthrough'].any())


if __name__ == '__main__':
    unittest.main()

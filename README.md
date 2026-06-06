# 保证金模型 — 黄金 & 白银 Wind 期货指数

> 最后更新: 2026-06-06

基于 EWMA 波动率和 VaR 方法的三阶段保证金计算模型，覆盖黄金 (Au) 和白银 (Ag) Wind 期货指数数据。

## 相关项目

- **[量化交易策略系统](https://github.com/jiqinghuang/trading_strategy)** — 10 种趋势跟踪策略回测框架
- **[个人网站](https://jiqinghuang.github.io/)** — 项目展示与投资专栏

## 架构

```
AUFI_WI.parquet ──┐
                  ├──> data_processor.py ──> processed_data.parquet ──┬──> stress_test.py
AGFI_WI.parquet ──┘                                                   └──> backtest.py ──> output_*.png
                                                                                       backtest_results.xlsx
```

### 第一阶段：数据处理 (`data_processor.py`)

- 加载 Wind 期货指数 parquet 文件（OHLCV 格式）
- 基于收盘价计算对数收益率
- 应用 EWMA 波动率模型（λ=0.98，RiskMetrics 风格衰减）
- 在对数正态假设下计算 99%、99.7%、99.99% 置信度的 VaR
- 输出 `processed_data.parquet`

### 第二阶段：压力测试 (`stress_test.py`)

三部分分析：
1. **N 日远期 VaR** — 将 EWMA 波动率乘以 √N，覆盖 [1, 1.8, 2, 2.8] 天
2. **手动波动率覆盖** — 固定波动率假设下的 VaR（Au 2%, Ag 4%）
3. **价格冲击情景** — 冲击后方差 λ·σ² + (1−λ)·ln(1+z)²，冲击幅度 2%–15%

### 第三阶段：回测 (`backtest.py`)

- **方法一** — 统计 |收益率| 同时超过 99% VaR 和最低阈值（Au 2%, Ag 4%）的天数，250 日滚动窗口
- **方法二** — 将波动率放大 √1.8 后重新计算 VaR，统计突破天数
- 生成每个品种的独立 PNG 图表（|收益率| vs 99% VaR 和 99.99% VaR）
- 导出 `backtest_results.xlsx`

## 快速开始

```bash
pip install numpy pandas scipy matplotlib openpyxl
python run_all.py
```

## 输出文件

| 文件 | 说明 |
|------|------|
| `processed_data.parquet` | 包含收益率、波动率、VaR 列的处理后数据 |
| `output_Au.png` | 黄金回测图 |
| `output_Ag.png` | 白银回测图 |
| `backtest_results.xlsx` | 回测结果（两种方法） |

## 数据

Wind 商品期货指数日线数据，包含列：`date`, `open`, `high`, `low`, `close`, `settle`, `volume`, `oi`, `amt`。模型仅使用 `close` 列进行定价。

- Au：2008-01-09 ~ 2026-06-06（约 4,460 行）
- Ag：2012-05-10 ~ 2026-06-06（约 3,400 行）

## 网站同步 (`sync_to_website.py`)

将模型结果同步到 [个人网站](https://jiqinghuang.github.io/)（GitHub Pages）的辅助脚本。

```bash
python sync_to_website.py
```

自动化流程：
1. 运行完整模型管道（data_processor → backtest）
2. 将 `output_Au.png` / `output_Ag.png` 复制到网站的 `assets/plots/` 目录
3. 更新 HTML 页面中的统计数据、日期范围和回测结果表格

需要本地存在 `jiqinghuang.github.io` 仓库。详细说明见 `SYNC_README.md`。

## 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `DECAY_FACTOR` | 0.98 | EWMA 衰减因子 λ |
| `TOLERANCE_LEVEL` | 0.01 | EWMA 初始化窗口容差（得到 k=228） |
| `ALPHA_LIST` | [0.01, 0.003, 0.0001] | VaR 置信水平（99%, 99.7%, 99.99%） |

## 方法说明

- **双尾 VaR**：使用 z_{α/2} 而非单尾 z_α，产生更保守的保证金估计（99% 下：z=2.576 vs z=2.326）
- **对数正态 VaR**：VaR = exp(z · σ) − 1，假设对数收益率服从 N(0, σ²)
- **EWMA**：初始化窗口 k=228，递推公式 v_{t+1} = λ·v_t + (1−λ)·r_t²

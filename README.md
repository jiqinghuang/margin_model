# 保证金模型 — 黄金 & 白银 Wind 期货指数

> 最后更新: 2026-09-18

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
- 基于收盘价计算对数收益率：
  $$r_t = \ln\!\left(1 + \frac{P_t - P_{t-1}}{P_{t-1}}\right)$$
- 应用 EWMA 波动率模型（λ=0.98，RiskMetrics 风格衰减）
  - 初始化：
    $$v_k = (1-\lambda)\sum_{i=0}^{k-1}\lambda^i \cdot r_{k-i}^2$$
  - 递推：
    $$v_{t+1}=\lambda\cdot v_t+(1-\lambda)\cdot r_t^2$$
  - 初始化窗口 $$k=\lceil\ln(\text{tol})/\ln(\lambda)\rceil=228$$（tol=0.01）
- 在对数正态假设下计算 99%、99.7%、99.99% 置信度的 VaR
- 输出 `processed_data.parquet`

### 第二阶段：压力测试 (`stress_test.py`)

三部分分析：
1. **N 日远期 VaR** — 将 EWMA 波动率乘以 √N，覆盖 [1, 1.8, 2, 2.8] 天
2. **手动波动率覆盖** — 固定波动率假设下的 VaR（Au 2%, Ag 4%）
3. **价格冲击情景** — 冲击后方差
   $$\lambda\cdot\sigma^2+(1-\lambda)\cdot\ln(1+z)^2$$
   冲击幅度 $$z \in \\{2\%,4\%,8\%,10\%,12\%,15\%\\}$$

### 第三阶段：回测 (`backtest.py`)

- **方法一** — 统计 |收益率| 同时超过 99% VaR 和最低阈值（Au 2%, Ag 4%）的天数，250 日滚动窗口
- **方法二** — 将方差放大 η=1.8 倍（标准差乘以 √1.8）后重新计算 VaR，统计突破天数
- 生成每个品种的独立 PNG 图表（|收益率| vs 99% VaR 和 99.99% VaR）
- 导出 `backtest_results.xlsx`

## 快速开始

```bash
pip install -r requirements.txt   # numpy/pandas/scipy/matplotlib/openpyxl/pyarrow + pillow(网站同步)
python run_all.py

# 单元测试
python -m unittest -v test_model

# 网站同步（另需本地存在 jiqinghuang.github.io 仓库）
python sync_to_website.py
```

## 输出文件

| 文件 | 说明 |
|------|------|
| `processed_data.parquet` | 包含收益率、波动率、VaR 列的处理后数据 |
| `output_Au.png` | 黄金回测图 |
| `output_Ag.png` | 白银回测图 |
| `stress_test_results.xlsx` | 压力测试三部分结果（N 日远期 VaR、手动波动率、价格冲击） |
| `backtest_results.xlsx` | 回测结果（两种方法） |

## 测试

```bash
python -m unittest -v test_model
```

覆盖：EWMA 递推公式、无前视（末笔收益冲击只影响预测行）、双尾 z 值、
预测行追加、数据源选择逻辑、突破计数的预热期不变量。

仓库配有 GitHub Actions（`.github/workflows/ci.yml`）：每次 push 自动运行本测试。

## 数据

Wind 商品期货指数日线数据，包含列：`date`, `open`, `high`, `low`, `close`, `settle`, `volume`, `oi`, `amt`。模型仅使用 `close` 列进行定价。

- Au：2008-01-09 ~ 2026-09-18（4,545 行）
- Ag：2012-05-10 ~ 2026-09-18（3,493 行）

> **数据行数说明**：上述行数为原始 parquet 中的交易日数。`data_processor` 会在序列末尾额外追加一行「下一交易日波动率预测」（index = 末日 + 1 天），因此模型内部 `len(df)` 会比上数多 1；`stress_test` 故意把该行当作「今日/预测日」使用。网站同步脚本（`sync_to_website.py`）取结束日与交易日数时以 `close` 非 NaN 的真实交易日为准。
>
> **数据源选择**：`data_processor.resolve_data_path` 会对比本目录与 `../trading_strategy/data/` 下同名 parquet 的截止日期，**自动选用更新的那份**（每日数据由 trading_strategy 的 `excel_to_parquet` 管道负责增量更新）。两者一致时用本地副本，因此本仓库单独克隆也能跑。

## 当前状态（2026-09-18 运行，数据源 trading_strategy/data）

最新一次完整管道运行结果。突破率分母为「VaR 有效且有已实现收益」的交易日
（排除 EWMA 预热期与末尾预测行）：

| 指标 | Au（黄金） | Ag（白银） |
|------|-----------|-----------|
| 数据区间 | 2008-01-09 ~ 2026-09-18 | 2012-05-10 ~ 2026-09-18 |
| VaR 覆盖交易日数 | 4,316 | 3,264 |
| 方法一突破数（含阈值） | 87（2.02%） | 57（1.75%） |
| 方法一 250 日滚动（最新） | 8 | 9 |
| 方法二突破数（η=1.8） | 39（0.90%） | 27（0.83%） |
| 方法二 250 日滚动（最新） | 5 | 1 |

详细解释与图表见 [个人网站](https://jiqinghuang.github.io/project-margin-model.html)。

## 网站同步 (`sync_to_website.py`)

将模型结果同步到 [个人网站](https://jiqinghuang.github.io/)（GitHub Pages）的辅助脚本。

```bash
python sync_to_website.py
```

自动化流程：
1. 运行完整模型管道（data_processor → backtest）
2. 将 `output_Au.png` / `output_Ag.png` 复制到网站的 `assets/plots/` 目录，**并同步生成 webp**（网站 `<picture>` 以 webp 优先，只更新 PNG 会让浏览器继续显示旧图）
3. 更新 HTML 页面中的统计数据、日期范围和回测结果表格——所有替换**校验恰好匹配一处**，页面结构变化时会报错终止而不是静默跳过
4. 按实际图片尺寸更新页面 `<img>` 的 `width`/`height`

需要本地存在 `jiqinghuang.github.io` 仓库和 Pillow（`pip install pillow`，缺失时跳过 webp）。详细说明见 `SYNC_README.md`。

## 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `DECAY_FACTOR` | 0.98 | EWMA 衰减因子 λ |
| `TOLERANCE_LEVEL` | 0.01 | EWMA 初始化窗口容差（得到 k=228） |
| `ALPHA_LIST` | [0.01, 0.003, 0.0001] | VaR 置信水平（99%, 99.7%, 99.99%） |

## 方法说明

- **双尾 VaR**：使用 $$z_{\alpha/2}$$ 而非单尾 $$z_\alpha$$，产生更保守的保证金估计（99% 下： $z=2.576$ vs $z=2.326$ ）
- **对数正态 VaR**：
  $$\text{VaR}=\exp(z\cdot\sigma)-1$$
  假设对数收益率服从 $$N(0,\sigma^2)$$
- **EWMA**：初始化窗口 $$k=228$$，递推公式
  $$v_{t+1}=\lambda\cdot v_t+(1-\lambda)\cdot r_t^2$$

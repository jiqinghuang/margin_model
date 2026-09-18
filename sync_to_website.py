"""
Sync margin model results to GitHub Pages.

This script:
1. Runs the margin model pipeline
2. Extracts summary statistics from backtest results
3. Copies plot images to the GitHub Pages assets folder
4. Updates the HTML file with new data values
"""

import re
import shutil
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # Pillow 缺失时跳过 webp 转换与尺寸更新，PNG 同步不受影响
    Image = None

# Paths
MARGIN_MODEL_DIR = Path(__file__).resolve().parent
GITHUB_PAGES_DIR = MARGIN_MODEL_DIR.parent / "jiqinghuang.github.io"
HTML_FILE = GITHUB_PAGES_DIR / "project-margin-model.html"
PLOTS_DIR = GITHUB_PAGES_DIR / "assets" / "plots"


def _sub_expect(pattern, repl, html, label):
    """执行一处正则替换并校验恰好匹配一次；否则说明页面结构已变化，
    静默跳过会导致网站数字停在旧值，这里直接报错终止同步。"""
    html, n = re.subn(pattern, repl, html)
    if n != 1:
        raise ValueError(
            f"网站页面结构可能已变化：{label} 预期匹配 1 处，实际 {n} 处"
        )
    return html


def run_margin_model():
    """Run the full margin model pipeline and return results."""
    print("=" * 70)
    print("Running margin model pipeline...")
    print("=" * 70)

    # Import and run data processor
    sys.path.insert(0, str(MARGIN_MODEL_DIR))
    from data_processor import run_data_processor
    from backtest import run_backtest

    # Run pipeline
    df_au, df_ag = run_data_processor()
    df_au_m1, df_ag_m1, df_au_m2, df_ag_m2 = run_backtest(df_au, df_ag)

    return {
        'df_au': df_au,
        'df_ag': df_ag,
        'df_au_m1': df_au_m1,
        'df_ag_m1': df_ag_m1,
        'df_au_m2': df_au_m2,
        'df_ag_m2': df_ag_m2,
    }


def extract_summary_stats(results: dict) -> dict:
    """Extract summary statistics from backtest results."""
    df_au = results['df_au']
    df_ag = results['df_ag']
    df_au_m1 = results['df_au_m1']
    df_ag_m1 = results['df_ag_m1']
    df_au_m2 = results['df_au_m2']
    df_ag_m2 = results['df_ag_m2']

    # Date ranges — use the last ACTUAL trading day (close is non-NaN),
    # not the trailing next-day forecast row appended by data_processor.
    au_start = df_au['close'].dropna().index[0].strftime('%Y-%m-%d')
    au_end = df_au['close'].dropna().index[-1].strftime('%Y-%m-%d')
    ag_start = df_ag['close'].dropna().index[0].strftime('%Y-%m-%d')
    ag_end = df_ag['close'].dropna().index[-1].strftime('%Y-%m-%d')

    # Total trading days = number of price observations (excludes forecast row)
    au_days = int(df_au['close'].notna().sum())
    ag_days = int(df_ag['close'].notna().sum())
    total_days = au_days + ag_days

    # Method 1 stats — 分母用 VaR 有效覆盖的交易日（排除 EWMA 预热期）
    au_m1_valid = int((df_au_m1['99.0% VaR'].notna() & df_au_m1['r_Au'].notna()).sum())
    au_m1_bt = int(df_au_m1['breakthrough'].sum())
    au_m1_days = au_m1_valid
    au_m1_rate = au_m1_bt / au_m1_days * 100
    au_m1_rolling = int(df_au_m1['250d_breakthroughs'].iloc[-1])

    ag_m1_valid = int((df_ag_m1['99.0% VaR'].notna() & df_ag_m1['r_Ag'].notna()).sum())
    ag_m1_bt = int(df_ag_m1['breakthrough'].sum())
    ag_m1_days = ag_m1_valid
    ag_m1_rate = ag_m1_bt / ag_m1_days * 100
    ag_m1_rolling = int(df_ag_m1['250d_breakthroughs'].iloc[-1])

    # Method 2 stats — 同样排除预热期
    au_m2_valid = int((df_au_m2['99.0% VaR'].notna() & df_au_m2['r_Au'].notna()).sum())
    au_m2_bt = int(df_au_m2['breakthrough'].sum())
    au_m2_days = au_m2_valid
    au_m2_rate = au_m2_bt / au_m2_days * 100
    au_m2_rolling = int(df_au_m2['250d_breakthroughs'].iloc[-1])

    ag_m2_valid = int((df_ag_m2['99.0% VaR'].notna() & df_ag_m2['r_Ag'].notna()).sum())
    ag_m2_bt = int(df_ag_m2['breakthrough'].sum())
    ag_m2_days = ag_m2_valid
    ag_m2_rate = ag_m2_bt / ag_m2_days * 100
    ag_m2_rolling = int(df_ag_m2['250d_breakthroughs'].iloc[-1])

    return {
        'au_start': au_start,
        'au_end': au_end,
        'ag_start': ag_start,
        'ag_end': ag_end,
        'total_days': total_days,
        'au_days': au_days,
        'ag_days': ag_days,
        'au_m1_bt': au_m1_bt,
        'au_m1_days': au_m1_days,
        'au_m1_rate': au_m1_rate,
        'au_m1_rolling': au_m1_rolling,
        'ag_m1_bt': ag_m1_bt,
        'ag_m1_days': ag_m1_days,
        'ag_m1_rate': ag_m1_rate,
        'ag_m1_rolling': ag_m1_rolling,
        'au_m2_bt': au_m2_bt,
        'au_m2_days': au_m2_days,
        'au_m2_rate': au_m2_rate,
        'au_m2_rolling': au_m2_rolling,
        'ag_m2_bt': ag_m2_bt,
        'ag_m2_days': ag_m2_days,
        'ag_m2_rate': ag_m2_rate,
        'ag_m2_rolling': ag_m2_rolling,
    }


def copy_plots():
    """Copy plot images from margin model to GitHub Pages.

    网站用 <picture> 且 webp 优先，因此这里同步生成 webp；
    只更新 PNG 会让支持 webp 的浏览器继续显示旧图。
    """
    print("\nCopying plot images...")

    # Ensure target directory exists
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    sizes = {}
    pairs = [
        (MARGIN_MODEL_DIR / "output_Au.png", PLOTS_DIR / "margin_model_Au.png"),
        (MARGIN_MODEL_DIR / "output_Ag.png", PLOTS_DIR / "margin_model_Ag.png"),
    ]
    for src, dst in pairs:
        shutil.copy2(src, dst)
        print(f"  Copied: {dst}")
        size = None
        if Image is not None:
            try:
                with Image.open(dst) as img:
                    size = img.size  # (width, height)
                    webp_dst = dst.with_suffix(".webp")
                    img.save(webp_dst, "WEBP", quality=90)
                    print(f"  Copied: {webp_dst}")
            except (OSError, ValueError) as exc:
                print(f"  警告: webp 转换失败 {dst.name}: {exc}")
        sizes[dst.stem] = size
    if Image is None:
        print("  警告: 未安装 Pillow，已跳过 webp 转换——网站 webp 图表不会更新！")
    return sizes


def update_img_dimensions(sizes):
    """按实际 PNG 尺寸更新网站 <img> 的 width/height（最佳努力，不阻断同步）。"""
    if Image is None:
        return
    html = HTML_FILE.read_text(encoding="utf-8")
    patched = 0
    for name, size in sizes.items():
        if size is None:
            continue
        width, height = size
        html, n = re.subn(
            r'(<img src="assets/plots/' + re.escape(name) + r'\.png"[^>]*'
            r'width=")\d+(" height=")\d+(")',
            rf"\g<1>{width}\g<2>{height}\g<3>",
            html,
            count=1,
        )
        patched += n
    HTML_FILE.write_text(html, encoding="utf-8")
    print(f"  图片尺寸已核对（更新 {patched}/{len(sizes)} 张）")


def update_html(stats: dict):
    """Update HTML file with new statistics."""
    print("\nUpdating HTML file...")

    # Read HTML
    html_content = HTML_FILE.read_text(encoding='utf-8')

    # Update total trading days
    html_content = _sub_expect(
        r'<div class="stat-number">~[\d,]+</div>',
        f'<div class="stat-number">~{stats["total_days"]:,}</div>',
        html_content,
        "交易天数统计",
    )

    # Update date ranges in captions
    # Au date range
    html_content = _sub_expect(
        r'<span data-lang="cn">黄金 \(Au\) — [\d-]+ ~ [\d-]+</span>'
        r'<span data-lang="en">Gold \(Au\) — [\d-]+ ~ [\d-]+</span>',
        f'<span data-lang="cn">黄金 (Au) — {stats["au_start"]} ~ {stats["au_end"]}</span>'
        f'<span data-lang="en">Gold (Au) — {stats["au_start"]} ~ {stats["au_end"]}</span>',
        html_content,
        "Au 日期范围",
    )

    # Ag date range
    html_content = _sub_expect(
        r'<span data-lang="cn">白银 \(Ag\) — [\d-]+ ~ [\d-]+</span>'
        r'<span data-lang="en">Silver \(Ag\) — [\d-]+ ~ [\d-]+</span>',
        f'<span data-lang="cn">白银 (Ag) — {stats["ag_start"]} ~ {stats["ag_end"]}</span>'
        f'<span data-lang="en">Silver (Ag) — {stats["ag_start"]} ~ {stats["ag_end"]}</span>',
        html_content,
        "Ag 日期范围",
    )

    # Update backtest results table row by row

    # Au Method 1
    html_content = _sub_expect(
        r'<td><strong>Au</strong></td>\s*'
        r'<td><span data-lang="cn">方法一（含阈值）</span><span data-lang="en">Method 1 \(w/ threshold\)</span></td>\s*'
        r'<td>\d+</td>\s*'
        r'<td>[\d,]+</td>\s*'
        r'<td>[\d.]+%</td>\s*'
        r'<td>\d+</td>',
        f'<td><strong>Au</strong></td>\n'
        f'              <td><span data-lang="cn">方法一（含阈值）</span><span data-lang="en">Method 1 (w/ threshold)</span></td>\n'
        f'              <td>{stats["au_m1_bt"]}</td>\n'
        f'              <td>{stats["au_m1_days"]:,}</td>\n'
        f'              <td>{stats["au_m1_rate"]:.2f}%</td>\n'
        f'              <td>{stats["au_m1_rolling"]}</td>',
        html_content,
        "Au 方法一表格行",
    )

    # Au Method 2
    html_content = _sub_expect(
        r'<td><strong>Au</strong></td>\s*'
        r'<td><span data-lang="cn">方法二（η=1\.8）</span><span data-lang="en">Method 2 \(η=1\.8\)</span></td>\s*'
        r'<td>\d+</td>\s*'
        r'<td>[\d,]+</td>\s*'
        r'<td>[\d.]+%</td>\s*'
        r'<td>\d+</td>',
        f'<td><strong>Au</strong></td>\n'
        f'              <td><span data-lang="cn">方法二（η=1.8）</span><span data-lang="en">Method 2 (η=1.8)</span></td>\n'
        f'              <td>{stats["au_m2_bt"]}</td>\n'
        f'              <td>{stats["au_m2_days"]:,}</td>\n'
        f'              <td>{stats["au_m2_rate"]:.2f}%</td>\n'
        f'              <td>{stats["au_m2_rolling"]}</td>',
        html_content,
        "Au 方法二表格行",
    )

    # Ag Method 1
    html_content = _sub_expect(
        r'<td><strong>Ag</strong></td>\s*'
        r'<td><span data-lang="cn">方法一（含阈值）</span><span data-lang="en">Method 1 \(w/ threshold\)</span></td>\s*'
        r'<td>\d+</td>\s*'
        r'<td>[\d,]+</td>\s*'
        r'<td>[\d.]+%</td>\s*'
        r'<td>\d+</td>',
        f'<td><strong>Ag</strong></td>\n'
        f'              <td><span data-lang="cn">方法一（含阈值）</span><span data-lang="en">Method 1 (w/ threshold)</span></td>\n'
        f'              <td>{stats["ag_m1_bt"]}</td>\n'
        f'              <td>{stats["ag_m1_days"]:,}</td>\n'
        f'              <td>{stats["ag_m1_rate"]:.2f}%</td>\n'
        f'              <td>{stats["ag_m1_rolling"]}</td>',
        html_content,
        "Ag 方法一表格行",
    )

    # Ag Method 2
    html_content = _sub_expect(
        r'<td><strong>Ag</strong></td>\s*'
        r'<td><span data-lang="cn">方法二（η=1\.8）</span><span data-lang="en">Method 2 \(η=1\.8\)</span></td>\s*'
        r'<td>\d+</td>\s*'
        r'<td>[\d,]+</td>\s*'
        r'<td>[\d.]+%</td>\s*'
        r'<td>\d+</td>',
        f'<td><strong>Ag</strong></td>\n'
        f'              <td><span data-lang="cn">方法二（η=1.8）</span><span data-lang="en">Method 2 (η=1.8)</span></td>\n'
        f'              <td>{stats["ag_m2_bt"]}</td>\n'
        f'              <td>{stats["ag_m2_days"]:,}</td>\n'
        f'              <td>{stats["ag_m2_rate"]:.2f}%</td>\n'
        f'              <td>{stats["ag_m2_rolling"]}</td>',
        html_content,
        "Ag 方法二表格行",
    )

    # Write updated HTML
    HTML_FILE.write_text(html_content, encoding='utf-8')
    print(f"  Updated: {HTML_FILE}")


def print_summary(stats: dict):
    """Print summary of changes."""
    print("\n" + "=" * 70)
    print("SYNC COMPLETE")
    print("=" * 70)
    print(f"\nDate ranges:")
    print(f"  Au: {stats['au_start']} ~ {stats['au_end']}")
    print(f"  Ag: {stats['ag_start']} ~ {stats['ag_end']}")
    print(f"\nTotal trading days: ~{stats['total_days']:,}")
    print(f"\nBacktest results:")
    print(f"  Au Method 1: {stats['au_m1_bt']} BT / {stats['au_m1_days']:,} days = {stats['au_m1_rate']:.2f}% (rolling: {stats['au_m1_rolling']})")
    print(f"  Au Method 2: {stats['au_m2_bt']} BT / {stats['au_m2_days']:,} days = {stats['au_m2_rate']:.2f}% (rolling: {stats['au_m2_rolling']})")
    print(f"  Ag Method 1: {stats['ag_m1_bt']} BT / {stats['ag_m1_days']:,} days = {stats['ag_m1_rate']:.2f}% (rolling: {stats['ag_m1_rolling']})")
    print(f"  Ag Method 2: {stats['ag_m2_bt']} BT / {stats['ag_m2_days']:,} days = {stats['ag_m2_rate']:.2f}% (rolling: {stats['ag_m2_rolling']})")
    print(f"\nFiles updated:")
    print(f"  - {PLOTS_DIR / 'margin_model_Au.png'}")
    print(f"  - {PLOTS_DIR / 'margin_model_Ag.png'}")
    print(f"  - {HTML_FILE}")


def main():
    """Main entry point."""
    # Verify paths exist
    if not MARGIN_MODEL_DIR.exists():
        print(f"Error: Margin model directory not found: {MARGIN_MODEL_DIR}")
        sys.exit(1)

    if not GITHUB_PAGES_DIR.exists():
        print(f"Error: GitHub Pages directory not found: {GITHUB_PAGES_DIR}")
        sys.exit(1)

    if not HTML_FILE.exists():
        print(f"Error: HTML file not found: {HTML_FILE}")
        sys.exit(1)

    # Run pipeline
    results = run_margin_model()

    # Extract stats
    stats = extract_summary_stats(results)

    # Copy plots (incl. webp)
    sizes = copy_plots()

    # Update HTML
    update_html(stats)
    update_img_dimensions(sizes)

    # Print summary
    print_summary(stats)


if __name__ == '__main__':
    main()

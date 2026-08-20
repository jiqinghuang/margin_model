# 同步保证金模型到个人网站

## 快速使用

每次更新数据后，只需运行一个命令即可同步到个人网站：

```bash
cd C:\Users\Jiqing\Desktop\repo\margin_model
python sync_to_website.py
```

## 脚本功能

`sync_to_website.py` 会自动完成以下操作：

1. **运行保证金模型管道**
   - 执行 `data_processor.py` 处理原始数据
   - 执行 `backtest.py` 进行回测分析

2. **复制图表文件**
   - 将 `output_Au.png` 复制到 `jiqinghuang.github.io/assets/plots/margin_model_Au.png`
   - 将 `output_Ag.png` 复制到 `jiqinghuang.github.io/assets/plots/margin_model_Ag.png`

3. **更新HTML文件**
   - 更新总交易日数统计
   - 更新Au和Ag的日期范围
   - 更新回测结果表格中的所有数值

## 更新的内容

### 统计数据
- 总交易日数（如 `~7,902`）

### 图表标题
- Au 日期范围（如 `2008-01-09 ~ 2026-06-13`）
- Ag 日期范围（如 `2012-05-10 ~ 2026-06-13`）

### 回测结果表格
| 品种 | 方法 | 总突破数 | 交易天数 | 突破率 | 250日滚动 |
|------|------|---------|---------|--------|----------|
| Au   | 方法一 | ✓ | ✓ | ✓ | ✓ |
| Au   | 方法二 | ✓ | ✓ | ✓ | ✓ |
| Ag   | 方法一 | ✓ | ✓ | ✓ | ✓ |
| Ag   | 方法二 | ✓ | ✓ | ✓ | ✓ |

## 文件路径

- **保证金模型目录**: `C:\Users\Jiqing\Desktop\repo\margin_model`
- **个人网站目录**: `C:\Users\Jiqing\Desktop\repo\jiqinghuang.github.io`
- **HTML文件**: `jiqinghuang.github.io\project-margin-model.html`
- **图表目录**: `jiqinghuang.github.io\assets\plots\`

## 工作流程

```
1. 更新原始数据 (AUFI_WI.parquet / AGFI_WI.parquet)
        ↓
2. 运行同步脚本
   python sync_to_website.py
        ↓
3. 自动完成:
   - 处理数据
   - 运行回测
   - 复制图表
   - 更新HTML
        ↓
4. 提交并推送到GitHub
   cd C:\Users\Jiqing\Desktop\repo\jiqinghuang.github.io
   git add .
   git commit -m "Update margin model data"
   git push
```

## 注意事项

1. **运行环境**: 需要安装 Python 及相关依赖（numpy, pandas, scipy, matplotlib）
2. **路径检查**: 脚本会自动验证所有路径是否存在
3. **备份**: 脚本会直接覆盖目标文件，如需保留旧版本请提前备份
4. **编码**: HTML文件使用 UTF-8 编码

## 手动更新（如需要）

如果只想更新特定部分，可以手动修改以下文件：

- **图表**: 直接复制 `margin_model/output_Au.png` 和 `output_Ag.png` 到 `jiqinghuang.github.io/assets/plots/`
- **HTML**: 编辑 `jiqinghuang.github.io/project-margin-model.html` 中的相应数值

## 故障排除

### 问题: 找不到文件
```
Error: Margin model directory not found: ...
```
**解决**: 确保在正确的目录下运行脚本

### 问题: 依赖缺失
```
ModuleNotFoundError: No module named 'xxx'
```
**解决**: 安装所需依赖
```bash
pip install numpy pandas scipy matplotlib
```

### 问题: 权限错误
**解决**: 确保对两个目录都有读写权限

## 更新频率建议

- **日常**: 每周运行一次以更新最新数据
- **重大市场事件**: 在剧烈波动后及时更新
- **新数据源**: 更换数据文件后立即更新

## 技术细节

脚本使用正则表达式匹配和替换HTML中的特定模式，确保只更新需要修改的部分，保持HTML结构和样式不变。

日期格式: `YYYY-MM-DD`
数值格式: 整数或两位小数百分比
千位分隔符: 使用逗号（如 `7,902`）

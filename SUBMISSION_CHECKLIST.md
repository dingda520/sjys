# Macro DataHub 提交清单

本清单按赛题《全球宏观经济指标数据要素采集与结构化服务》的提交要求整理。

## 1. 参赛报告

建议基于以下文件扩写正式报告：

```text
report_outline.md
```

报告应包含：

- 背景理解
- 总体方案
- 指标体系
- 数据源说明
- 技术架构
- 性能测试
- 结果展示
- 应用价值分析
- 合规性与边界说明

## 2. 源代码

核心源代码：

```text
app.py
frontend/index.html
frontend/showcase.html
```

后端包含：

- World Bank 数据接入
- BLS 数据接入
- Eurostat 数据接入
- IMF DataMapper / WEO 数据接入
- OECD SDMX 数据接入
- ECB Data API 数据接入
- BIS Statistics API 数据接入
- 指标标准化
- JSON 查询接口
- 批量查询接口
- 质量校验
- 国家对比
- 指标搜索
- 可视化数据输出
- 自动解读与报告段落输出
- 跨源一致性校验
- 缓存与失败重试

## 3. 运行说明

运行说明文件：

```text
README.md
README_DEPLOY.md
START_HERE.bat
START_ANACONDA.bat
```

本地运行：

```text
双击 START_HERE.bat
```

浏览器访问：

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/showcase
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/evaluation
http://127.0.0.1:8000/consistency
```

## 4. 指标字典与映射表

启动服务时自动生成：

```text
data/indicator_dictionary.csv
data/source_mapping.csv
data/country_dictionary.csv
```

这些文件对应赛题要求中的：

- 标准指标编码
- 中文名和英文名
- 原始来源编码
- 单位
- 频率
- 国家覆盖
- 来源机构与数据集

## 5. 示例查询

示例查询文件：

```text
examples/sample_queries.json
```

当前提供 33 条示例查询，满足最低验收要求中的“至少 20 条示例查询”。

## 6. 样例输出

可以在服务启动后打开以下接口生成样例 JSON：

```text
http://127.0.0.1:8000/series?country=CN&indicator_code=GDP_NOMINAL&start_date=2018&end_date=2024&frequency=A
http://127.0.0.1:8000/series?country=US&indicator_code=CPI_YOY&start_date=2020-01&end_date=2025-12&frequency=M
http://127.0.0.1:8000/series?country=DE&indicator_code=INDUSTRIAL_PRODUCTION&start_date=2023-01&end_date=2024-12&frequency=M
http://127.0.0.1:8000/series?country=US&indicator_code=IMF_GDP_GROWTH&start_date=2020&end_date=2024&frequency=A
http://127.0.0.1:8000/series?country=US&indicator_code=OECD_CPI_YOY&start_date=2024-01&end_date=2024-12&frequency=M
http://127.0.0.1:8000/series?country=EA&indicator_code=ECB_EUR_USD&start_date=2024-01&end_date=2024-12&frequency=M
http://127.0.0.1:8000/series?country=US&indicator_code=BIS_POLICY_RATE&start_date=2024-01&end_date=2024-12&frequency=M
http://127.0.0.1:8000/compare?countries=US,CN,DE,JP,GB,IN,FR&indicator_code=GDP_NOMINAL&date=2023&frequency=A
http://127.0.0.1:8000/visualization?country=CN&indicator_code=GDP_NOMINAL&start_date=2018&end_date=2024&frequency=A
http://127.0.0.1:8000/insight?country=IN&indicator_code=TRADE_BALANCE&start_date=2018&end_date=2024&frequency=A
http://127.0.0.1:8000/consistency
http://127.0.0.1:8000/evaluation
```

建议截图：

- 首页查询界面
- 主界面“评审看板”
- 展示版首页 `/showcase`
- 指标趋势图
- 自动解读与答辩摘要卡片
- 标准化 JSON 输出
- 数据质量校验
- 跨源一致性校验页面
- `/docs` API 文档页
- `/compare` 国家对比 JSON
- `/consistency` 跨源一致性 JSON
- `/evaluation` 评审证据 JSON

## 7. 自检命令

不联网自检：

```text
C:\Users\JackpoT\anaconda3\python.exe tests\smoke_test.py
```

联网自检：

```text
C:\Users\JackpoT\anaconda3\python.exe tests\smoke_test.py --online
```

## 8. 最低验收要求对照

| 最低要求 | 项目对应 |
| --- | --- |
| 能够成功运行 | `START_HERE.bat` |
| 至少 20 条示例查询 | `examples/sample_queries.json` |
| 标准化 JSON | `/series`、`/batch-query` |
| 来源机构与数据集 | `series.source` |
| 非手工 Excel | 官方 API 程序化查询 |
| 不输出黑盒数据 | `source_url`、`source_series_code`、`quality_report` |
| 不同来源一致性展示 | `/consistency` 与首页“跨源一致性”页面 |
| 结果可解释性展示 | 首页“自动解读”卡片与 `/insight` JSON |

## 9. 风险说明

- BLS 官方 API 在部分网络环境下可能 SSL 握手超时，系统已加入重试和结构化错误返回。
- 当前 V1 已接入 World Bank、BLS、Eurostat、IMF、OECD、ECB、BIS 7 个官方来源；后续可继续加深每个来源的指标覆盖。
- 当前缓存为文件缓存，适合演示和轻量部署；正式生产环境可升级到 SQLite 或 DuckDB。

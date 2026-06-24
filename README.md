# 经观 EconView

这是一次性重写的 Windows 友好版本，重点解决：

- 不依赖 `py`
- 不依赖 PATH 里的 `python`
- 不依赖 `pip install`
- 不依赖 `uvicorn`
- 不依赖 FastAPI
- 可以直接使用你电脑上的 Anaconda Python：`C:\Users\JackpoT\anaconda3\python.exe`

## 项目定位

经观 EconView 是一个面向全球宏观经济数据查询、标准化、质量治理和展示的轻量级平台。它把 World Bank、BLS、Eurostat、IMF、OECD、ECB、BIS 等官方公开数据源统一封装成同一种 JSON 输出，适合用于：

- 参赛项目演示
- 毕业论文系统原型
- 宏观数据查询网页
- AI Agent 工具调用
- ECharts / Dashboard 可视化
- 研究脚本的数据接口

## 真实数据展示材料

为了证明网页的可用性和实用性，项目已基于线上站点 `https://sjys-th73.onrender.com/` 采集真实接口返回，并生成报告补充材料：

```text
docs/TECHNICAL_DESCRIPTION_REAL_DATA.md
docs/REPORT_BODY_REAL_DATA.md
docs/real_data_evidence/summary.json
docs/real_data_evidence/raw_online_responses.json
docs/real_data_evidence/assets/*.svg
```

这些材料没有使用模拟数据。示例包括中国名义 GDP、美国 CPI 同比（BLS）、美国 CPI 同比（OECD）、欧元区 HICP 同比、IMF 美国 GDP 增速、ECB 欧元兑美元汇率、BIS 美国政策利率，以及 2023 年主要经济体 GDP 横向对比。

正式展示时建议按“首页能力概览 → 中国 GDP → 美国 CPI → OECD CPI 复核 → 多国 GDP 对比 → JSON/Schema/Capabilities”的顺序演示，既能体现网页可视化，也能体现可程序化调用的数据服务能力。

## 开发流程

本项目按企业开发流程推进，不一次性推倒重写。

当前开发分支：

```text
feature/schema-v2
```

推荐日常流程：

```text
git status
运行 tests\smoke_test.py
确认页面和接口正常
git add .
git commit -m "本次完成的功能"
```

已完成 Sprint：

```text
Sprint 1: Git + 项目重构 + Unified Response Schema
Sprint 2: Metadata / Quality / Lineage 基础模块化
Sprint 3: Agent Ready API
Sprint 4: Visualization API + Eurostat + IMF/OECD/ECB/BIS + Cross-source Consistency
```

本阶段新增：

```text
app/models/observation.py
app/models/metadata.py
app/models/quality.py
app/models/lineage.py
app/models/response.py
docs/DEVELOPMENT_PLAN.md
```

这些模型先不改变一键运行方式，而是作为后续模块化、Agent 接入、质量治理和论文架构说明的基础。

Sprint 2 新增：

```text
app/services/quality_check.py
app/services/standardizer.py
app/services/lineage.py
```

`app.py` 现在通过 service 层完成标准化输出、错误响应、质量校验和数据血缘生成；原来的 Web 页面和 API 调用方式保持不变。

Sprint 3 新增：

```text
GET /agent-tools
GET /error-catalog
GET /openapi-lite
```

这些接口面向 AI Agent 和自动化调用：

- `/agent-tools`：告诉 Agent 可以调用哪些工具、参数是什么、何时使用。
- `/error-catalog`：告诉 Agent 错误码是什么意思、失败后怎么恢复。
- `/openapi-lite`：提供轻量接口契约，便于自动生成调用逻辑。

## 1. 最推荐运行方式

解压后，双击：

```text
START_HERE.bat
```

它会自动寻找：

```text
%USERPROFILE%\anaconda3\python.exe
%USERPROFILE%\miniconda3\python.exe
其他 PATH 中的 python.exe
```

启动成功后会自动打开浏览器。

首页：

```text
http://127.0.0.1:8000
```

展示版首页：

```text
http://127.0.0.1:8000/showcase
```

API 文档：

```text
http://127.0.0.1:8000/docs
```

## 2. 如果你想强制使用 Anaconda

双击：

```text
START_ANACONDA.bat
```

这个脚本固定使用：

```text
C:\Users\JackpoT\anaconda3\python.exe
```

实际脚本里使用的是 `%USERPROFILE%\anaconda3\python.exe`，所以换电脑用户名也能用。

## 3. 本版本已实现内容

### 数据源

- World Bank Indicators API
- U.S. Bureau of Labor Statistics Public Data API
- Eurostat Statistics API
- IMF DataMapper / WEO API
- OECD SDMX API
- ECB Data API
- BIS Statistics API

### 指标

World Bank 年度指标：

- GDP_NOMINAL
- GDP_REAL_GROWTH
- EXPORTS
- IMPORTS
- TRADE_BALANCE

BLS 美国月度指标：

- CPI_LEVEL
- CPI_YOY
- UNEMP_RATE
- NONFARM_PAYROLL

Eurostat 欧洲月度指标：

- HICP_YOY
- PPI_LEVEL
- INDUSTRIAL_PRODUCTION
- RETAIL_SALES_VOLUME
- LONG_TERM_RATE

IMF 年度指标：

- IMF_GDP_GROWTH

OECD 月度指标：

- OECD_CPI_YOY

ECB 月度指标：

- ECB_EUR_USD

BIS 月度指标：

- BIS_POLICY_RATE

### 接口

```text
GET /health
GET /showcase
GET /capabilities
GET /schema
GET /agent-tools
GET /error-catalog
GET /openapi-lite
GET /countries
GET /indicators
GET /search-indicators
GET /series
GET /compare
GET /visualization
GET /insight
GET /consistency
GET /cache-stats
GET /evaluation
POST /batch-query
GET /sample-queries
GET /docs
```

示例：

```text
http://127.0.0.1:8000/series?country=US&indicator_code=CPI_YOY&start_date=2020-01&end_date=2025-12&frequency=M
```

更适合答辩展示的页面：

```text
http://127.0.0.1:8000/showcase
```

中国名义 GDP：

```text
http://127.0.0.1:8000/series?country=CN&indicator_code=GDP_NOMINAL&start_date=2018&end_date=2024&frequency=A
```

可视化格式：

```text
http://127.0.0.1:8000/visualization?country=CN&indicator_code=GDP_NOMINAL&start_date=2018&end_date=2024&frequency=A
```

自动解读与报告段落：

```text
http://127.0.0.1:8000/insight?country=IN&indicator_code=TRADE_BALANCE&start_date=2018&end_date=2024&frequency=A
```

国家对比：

```text
http://127.0.0.1:8000/compare?countries=US,CN,DE,JP,GB,IN,FR&indicator_code=GDP_NOMINAL&date=2023&frequency=A
```

Eurostat 工业生产：

```text
http://127.0.0.1:8000/series?country=DE&indicator_code=INDUSTRIAL_PRODUCTION&start_date=2023-01&end_date=2024-12&frequency=M
```

IMF / OECD / ECB / BIS 代表性查询：

```text
http://127.0.0.1:8000/series?country=US&indicator_code=IMF_GDP_GROWTH&start_date=2020&end_date=2024&frequency=A
http://127.0.0.1:8000/series?country=US&indicator_code=OECD_CPI_YOY&start_date=2024-01&end_date=2024-12&frequency=M
http://127.0.0.1:8000/series?country=EA&indicator_code=ECB_EUR_USD&start_date=2024-01&end_date=2024-12&frequency=M
http://127.0.0.1:8000/series?country=US&indicator_code=BIS_POLICY_RATE&start_date=2024-01&end_date=2024-12&frequency=M
```

跨源一致性校验：

```text
http://127.0.0.1:8000/consistency
http://127.0.0.1:8000/consistency?online=1
```

指标搜索：

```text
http://127.0.0.1:8000/search-indicators?q=gdp
http://127.0.0.1:8000/search-indicators?q=失业&frequency=M
```

能力说明：

```text
http://127.0.0.1:8000/capabilities
```

统一返回结构说明：

```text
http://127.0.0.1:8000/schema
```

Agent 工具说明：

```text
http://127.0.0.1:8000/agent-tools
http://127.0.0.1:8000/error-catalog
http://127.0.0.1:8000/openapi-lite
```

缓存状态：

```text
http://127.0.0.1:8000/cache-stats
```

评审证据：

```text
http://127.0.0.1:8000/evaluation
```

## 4. 标准化 JSON 输出

`GET /series` 返回统一结构：

```json
{
  "request": {
    "country": "CN",
    "indicator_code": "GDP_NOMINAL",
    "start_date": "2018",
    "end_date": "2024",
    "frequency": "A"
  },
  "series": {
    "series_id": "CN.GDP_NOMINAL.A",
    "indicator_code": "GDP_NOMINAL",
    "indicator_name_zh": "名义 GDP",
    "country_code": "CN",
    "frequency": "A",
    "unit": "current US$",
    "source": {
      "organization": "World Bank",
      "dataset": "World Development Indicators",
      "source_series_code": "NY.GDP.MKTP.CD"
    },
    "observations": []
  },
  "quality_report": {
    "observation_count": 0,
    "missing_period_count": 0,
    "duplicate_records": 0,
    "outlier_count": 0,
    "traceable_source": true,
    "passed": false
  },
  "error": null
}
```

## 5. 生成的参赛材料

启动时会自动生成：

```text
data/indicator_dictionary.csv
data/source_mapping.csv
data/country_dictionary.csv
examples/sample_queries.json
```

这些可以直接作为参赛材料的一部分。

## 6. 本地自检

默认自检不联网，只验证项目结构、Schema、能力说明和校验逻辑：

```text
C:\Users\JackpoT\anaconda3\python.exe tests\smoke_test.py
```

如果要同时测试官方 API：

```text
C:\Users\JackpoT\anaconda3\python.exe tests\smoke_test.py --online
```

注意：`--online` 依赖当前网络能访问 World Bank / BLS / Eurostat / IMF / OECD / ECB / BIS。BLS 或国际组织接口在部分网络环境下可能出现 SSL 握手或上游超时，系统已经加入自动重试和清晰错误返回。

## 7. 可作为项目亮点写进报告

- 7 个官方公开 API 接入，不使用手工 Excel 替代系统能力。
- 统一指标编码、国家编码、频率、单位和来源元数据。
- 输出标准化 JSON，可被前端、Agent、研究脚本复用。
- 自动质量校验：缺失期、重复值、异常波动、来源可追溯。
- 支持 ECharts 友好的 `/visualization` 输出。
- 支持 `/insight` 自动生成中文解读、报告段落和答辩要点。
- 支持 `/compare` 多国家横向对比，体现业务展示能力。
- 支持 `/consistency` 跨源一致性校验，证明多源共享统一 Schema、质量报告和来源血缘。
- 支持 `/search-indicators` 指标检索，体现指标治理能力。
- 主界面内置“评审看板”，集中展示最低验收、评分维度、项目证据和演示路径。
- 支持 `/evaluation` 结构化评审证据，方便答辩和材料复核。
- 支持 `/showcase` 展示版界面，适合答辩、视频录屏和第一眼演示。
- 支持 `/capabilities`、`/schema` 和 `/insight`，便于 AI Agent 理解工具能力并输出可读结论。
- 零外部依赖，Windows 双击即可运行，降低演示环境风险。

## 8. 对照赛题最低验收要求

| 要求 | 当前完成情况 |
| --- | --- |
| 至少 20 条示例查询 | `examples/sample_queries.json` 已提供 33 条 |
| 标准化 JSON 输出 | `/series`、`/batch-query` 已支持 |
| 说明来源机构与数据集 | 每条结果包含 `source.organization`、`source.dataset`、`source_series_code` |
| 非手工 Excel | 通过官方 API 程序化查询，CSV 仅作为字典和提交材料 |
| 来源可追溯 | 返回 `source_url`、官方代码、数据集和质量报告 |
| 查询工具可运行 | 双击 `START_HERE.bat` 启动 Web + API |
| 批量查询 | `POST /batch-query` 支持 |
| 质量校验 | 返回 `quality_report` |
| 结果展示 | 首页趋势图、自动解读、JSON 输出、质量校验、`/compare` 国家对比、跨源一致性页面 |

## 9. 下一阶段扩展路线

建议按下面顺序扩展：

1. 继续加深 IMF / OECD / ECB / BIS 指标覆盖，例如 IFS、劳动力、金融市场和信贷指标。
2. 增加本地 SQLite 或 DuckDB 缓存层，记录历史查询和更新时间。
3. 增加更多月度指标，如 M2、住房、财政和景气调查指标。
4. 增加修订历史追踪和更细的数值级跨源一致性校验。
5. 增加论文附录：API 说明、数据字典、系统架构图、示例输出。

## 10. 注意

本项目默认访问官方公开 API，因此首次查询需要联网。查询结果会缓存到：

```text
cache/
```

重复查询会优先读取缓存，速度更快。

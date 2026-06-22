# 参赛报告提纲

## 1. 背景理解

宏观经济指标是金融市场研究、资产配置、政策分析、风险预警和智能投研系统的重要基础数据。全球宏观数据存在来源分散、口径不一、频率不统一、单位混杂、修订频繁等问题，因此需要构建统一、可追溯、可程序化调用的数据服务。

## 2. 项目目标

本项目构建 Macro DataHub：全球宏观经济指标采集与结构化查询系统。系统能够接入官方公开数据源，对指标进行统一编码和元数据治理，并输出标准化 JSON。

## 3. 数据源

V1 已接入：

- World Bank Indicators API
- U.S. Bureau of Labor Statistics Public Data API

后续可扩展：

- IMF
- OECD
- Eurostat
- ECB
- BIS

## 4. 指标体系

V1 覆盖：

- GDP_NOMINAL
- GDP_REAL_GROWTH
- EXPORTS
- IMPORTS
- TRADE_BALANCE
- CPI_LEVEL
- CPI_YOY
- UNEMP_RATE
- NONFARM_PAYROLL

## 5. 技术架构

数据源 API → 接入层 → 标准化层 → 质量校验层 → HTTP 查询服务 → 前端展示 / JSON 输出

### 5.1 系统模块

- 数据源连接器：负责访问 World Bank、BLS 等官方公开 API。
- 指标字典：维护标准指标编码、中文名、英文名、频率、单位、计算方式。
- 来源映射：维护标准指标与官方源序列代码之间的关系。
- 标准化服务：把不同来源的原始数据统一为同一种 JSON 结构。
- 质量校验服务：检查观测值数量、缺失、重复、异常和来源可追溯性。
- Web API 服务：提供 `/series`、`/batch-query`、`/visualization` 等接口。
- 前端展示：提供查询表单、趋势图、元数据摘要、JSON 输出和质量报告。
- 指标检索：提供 `/search-indicators`，支持按关键词、数据源和频率查找指标。
- 国家对比：提供 `/compare`，支持多国家同一指标横向比较。
- 缓存诊断：提供 `/cache-stats`，展示文件缓存数量与缓存策略。
- 评审证据：提供 `/evaluation` 和主界面“评审看板”，集中展示最低验收、评分维度、项目证据和推荐演示路径。

### 5.2 数据流

用户选择国家、指标、频率和时间区间后，系统先根据指标字典找到数据源映射，再调用官方 API 获取原始数据。原始数据经过解析和标准化后生成统一 JSON，同时自动生成质量报告。前端直接使用该 JSON 绘制趋势图并展示元数据。

## 6. 标准化 JSON 输出

字段包括：

- request
- series
- indicator_code
- country_code
- frequency
- unit
- seasonal_adjustment
- calculation
- source
- last_updated
- observations
- quality_report
- error

### 6.1 统一 Schema 的意义

不同官方数据源的数据格式差异很大。如果每个数据源都直接暴露原始格式，前端、研究脚本和 AI Agent 都需要分别适配。统一 Schema 后，所有数据源最终都输出同一种结构，从而降低扩展成本，并提高系统可维护性。

### 6.2 Agent 友好接口

系统新增：

- `/capabilities`：机器可读的系统能力说明，包括数据源、指标、国家、接口列表。
- `/schema`：统一返回结构说明，便于 Agent 生成正确请求和解析结果。
- `/visualization`：返回 ECharts 友好的图表数据，便于自动生成可视化看板。
- `/search-indicators`：返回指标字典检索结果，便于用户或 Agent 找到合适指标。
- `/compare`：返回多国家横向比较结果，便于宏观研究场景展示。
- `/evaluation`：返回赛题验收与评分点对照，便于答辩复核。

## 7. 数据质量校验

包括：

- 观测值数量
- 缺失期数
- 重复观测值
- 异常值提醒
- 单位一致性
- 来源可追溯

质量校验不替代官方数据审核，但可以在系统层面发现常见问题。例如时间区间内没有数据、月份缺失、重复观测值、单位为空、来源元数据不完整等。对于 CPI 同比这类派生指标，系统还会在观测值中记录计算方法和基准期。

## 8. 运行与演示

双击 START_HERE.bat 即可运行，无需 pip、uvicorn 或 PATH 配置。

演示建议：

1. 打开首页，展示左侧功能菜单和已实现数据源。
2. 查询“中国名义 GDP”，说明 World Bank 官方 API 接入。
3. 查询“美国 CPI 同比”，说明 BLS 月度数据与同比计算。
4. 打开 JSON 输出页，展示标准化结构。
5. 打开质量校验页，说明缺失、重复、异常和来源可追溯检查。
6. 打开 `/docs`、`/capabilities`、`/schema`，说明系统不仅是网页，也是一套可程序化调用的数据服务。
7. 打开 `/compare`，展示多国家横向比较能力。
8. 打开 `/search-indicators?q=gdp`，展示指标治理和检索能力。
9. 打开主界面“评审看板”或 `/evaluation`，展示项目与评分标准的对应关系。

验收材料：

- `data/indicator_dictionary.csv`
- `data/source_mapping.csv`
- `data/country_dictionary.csv`
- `examples/sample_queries.json`
- `/series` 示例 JSON 输出
- `/visualization` 图表数据输出
- `/compare` 国家对比输出
- `/search-indicators` 指标检索输出

## 9. 应用价值

系统可用于金融研究看板、AIGC/Agent 工具调用、宏观数据查询、跨国指标比较和策略研究数据底座。

## 10. 项目创新点

- 面向多源宏观数据的统一 Schema，而不是简单爬取单一表格。
- 同时服务网页展示、API 调用、AI Agent 和可视化输出。
- 把数据来源、单位、频率、口径、更新时间和质量校验放入同一个响应结构。
- 使用零依赖架构降低本地演示失败风险，适合比赛和答辩现场运行。
- 设计了可扩展数据源体系，后续可接入 IMF、OECD、Eurostat、ECB 和 BIS。
- 将指标搜索、国家对比、图表输出和 Schema 描述统一封装为 API，便于复用。

## 11. 局限与改进

- V1 只实现 World Bank 和 BLS，全球高频宏观数据覆盖还不完整。
- BLS 在部分网络环境下可能出现 SSL 握手超时，需要依赖重试、缓存或备用网络。
- 当前缓存是文件缓存，后续可以升级为 SQLite / DuckDB。
- 当前质量校验是规则型，后续可增加修订历史、异常解释和跨源一致性检查。

## 12. 下一步计划

1. 接入 OECD 和 Eurostat，补齐发达经济体高频指标。
2. 增加 IMF 和 BIS，覆盖财政、外部部门、利率、信贷等指标。
3. 增加本地数据库缓存，提升重复查询速度和稳定性。
4. 增加修订历史追踪和跨源一致性校验。
5. 生成论文中的系统架构图、数据流图和示例 JSON 附录。

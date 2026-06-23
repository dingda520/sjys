# 经观 EconView 开发拆解

这份文档把项目按企业开发流程拆成可执行 Sprint。当前代码仍保留一键运行版本，后续逐步模块化，不一次性推倒重写。

## Sprint 1: Git + Unified Response Schema

目标：让项目可以持续开发、可回退、可审查。

已完成内容：

- 初始化 Git 仓库。
- 建立开发分支 `feature/schema-v2`。
- 新增 `.gitignore`，避免缓存和日志进入版本库。
- 新增 `app/models/`，定义统一响应模型：
  - `Observation`
  - `SourceMetadata`
  - `SeriesMetadata`
  - `QualityReport`
  - `DataLineage`
  - `QueryRequest`
  - `ErrorInfo`
  - `StandardResponse`

## Sprint 2: Metadata / Quality / Lineage

目标：把现有 `app.py` 中的元数据、质量报告和来源追踪逻辑逐步迁移到可复用服务。

已完成基础拆分：

- 新增 `app/services/standardizer.py`，负责统一响应和错误响应。
- 新增 `app/services/quality_check.py`，负责缺失、重复、异常、单位和追溯检查。
- 新增 `app/services/lineage.py`，负责生成来源追踪信息。
- `app.py` 保留兼容包装函数，现有接口不用改。
- `/series` 响应新增 `lineage` 字段，用于记录 provider、dataset、api_url、retrieved_at 等信息。

后续增强：

- 继续把具体数据源连接器拆到 `app/connectors/`。
- 把国家、指标、来源字典迁移到 `app/registry/` 或配置文件。
- 为 `lineage` 增加修订版本和缓存命中信息。

## Sprint 3: Agent Ready API

目标：让 AI Agent 能理解和调用系统能力。

已完成内容：

- 强化 `/capabilities`，增加 `agent_ready`、`agent_entrypoints` 和推荐调用流程。
- 强化 `/schema`，增加查询参数 schema、示例路径、Agent 使用规则。
- 新增 `/agent-tools`，提供工具名称、用途、参数、返回字段和使用场景。
- 新增 `/error-catalog`，提供错误码含义和 Agent 恢复建议。
- 新增 `/openapi-lite`，提供轻量 OpenAPI 风格接口契约。

后续增强：

- 将 `/agent-tools` 转换为 OpenAI tool/function calling JSON Schema。
- 增加自然语言到指标编码的示例集。
- 为 Agent 添加安全规则：无法联网或上游失败时不得编造数据。

## Sprint 4: Visualization API

目标：让数据服务直接支持看板。

已完成内容：

- 完善 `/visualization`，增加摘要、表格数据、ECharts toolbox/dataZoom 和 lineage。
- 完善 `/compare`，增加排名、格式化数值、摘要和增强柱状图配置。
- 新增 Eurostat 连接器，补充 HICP、PPI、工业生产、零售销售、长期利率等月度指标。
- 新增 IMF、OECD、ECB、BIS 代表性连接器，覆盖 IMF GDP 增长、OECD CPI 同比、ECB 汇率、BIS 政策利率。
- 新增 `/consistency`，用于校验 World Bank、BLS、Eurostat、IMF、OECD、ECB、BIS 的统一 Schema、来源映射、质量报告和血缘字段。
- 首页新增“跨源一致性”页面，并支持在线代表性接口抽检。
- 新增 `/insight` 自动解读接口和首页答辩摘要卡片，用于把查询结果转成中文报告段落。

后续增强：

- 增加更多图表类型。
- 将数值级跨源比对从结构校验扩展到同一指标不同来源的抽样复核。

## Sprint 5: Tests / Docs / Submission

目标：让项目可复现、可提交、可答辩。

计划任务：

- 已扩展 `tests/smoke_test.py`，继续维护离线结构校验和联网代表性接口抽检。
- 补充正式参赛报告。
- 生成系统架构图和数据流图。
- 整理提交压缩包清单。

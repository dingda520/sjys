# 技术说明：基于线上真实数据的可用性验证

本文档说明经观 EconView 线上网页（`https://sjys-th73.onrender.com/`）如何体现可用性、实用性和可展示性。本文档中的数字均来自线上接口的真实返回，原始响应已保存到 `docs/real_data_evidence/raw_online_responses.json`，汇总结果保存到 `docs/real_data_evidence/summary.json`。

## 1. 系统能力概览

线上 `/capabilities` 与 `/consistency` 返回显示，系统当前已接入 7 个官方数据源、18 个标准指标、8 个国家或地区，并提供 33 条示例查询。数据源包括 World Bank、BLS、Eurostat、IMF、OECD、ECB 和 BIS。

系统对外暴露的核心接口包括 `/series`、`/batch-query`、`/compare`、`/visualization`、`/insight`、`/consistency`、`/evaluation`、`/schema`、`/agent-tools`、`/error-catalog`、`/openapi-lite`、`/sample-queries` 和 `/capabilities`。这说明网页不仅是可视化页面，也是一套可由程序、脚本或 Agent 调用的数据服务。

## 2. 真实数据验证样例

| 场景 | 接口参数 | 数据源 | 返回观测值 | 质量校验 | 最新值 |
|---|---|---:|---:|---:|---:|
| 中国名义 GDP | `CN / GDP_NOMINAL / 2020-2023 / A` | World Bank | 4 | 通过 | 2023 年，18.27 万亿美元 |
| 美国 CPI 同比 | `US / CPI_YOY / 2023-01 至 2025-12 / M` | BLS | 35 | 通过 | 2025-12，2.6533% |
| 美国 CPI 同比 | `US / OECD_CPI_YOY / 2024-01 至 2024-12 / M` | OECD | 12 | 通过 | 2024-12，2.8881% |
| 欧元区 HICP 同比 | `EA / HICP_YOY / 2023-01 至 2024-12 / M` | Eurostat | 24 | 通过 | 2024-12，2.4% |
| 美国实际 GDP 增速 | `US / IMF_GDP_GROWTH / 2021-2024 / A` | IMF | 4 | 通过 | 2024 年，2.8% |
| 欧元兑美元汇率 | `EA / ECB_EUR_USD / 2024-01 至 2024-12 / M` | ECB | 12 | 通过 | 2024-12，1.047875 USD per EUR |
| 美国政策利率 | `US / BIS_POLICY_RATE / 2024-01 至 2024-12 / M` | BIS | 12 | 通过 | 2024-12，4.375% |

这些结果体现了三点：第一，系统能够访问多个真实官方源；第二，同一套前端和 JSON Schema 可以展示年度、月度、水平值、同比、汇率和利率等不同类型指标；第三，每个结果都带有质量报告、来源信息、单位、频率和观测值列表，便于复核。

## 3. 可视化展示建议

正式展示时建议使用四类图表：

1. **趋势图**：展示美国 CPI 同比、OECD 美国 CPI 同比、欧元区 HICP 同比等月度数据，证明系统可以处理高频时间序列。
2. **年度折线图**：展示中国名义 GDP 2020-2023 年变化，证明系统可以接入 World Bank 年度宏观指标。
3. **横向对比条形图**：展示 2023 年主要经济体名义 GDP，证明 `/compare` 能支持多国家同指标比较。
4. **质量证据表**：展示观测值数量、缺失期数、重复记录、异常值、单位一致性和来源可追溯性，证明系统不是单纯画图，而是有数据治理能力。

已生成的真实数据图表如下：

![美国 CPI 同比（BLS）](real_data_evidence/assets/us_bls_cpi_yoy.svg)

![美国 CPI 同比（OECD）](real_data_evidence/assets/us_oecd_cpi_yoy.svg)

![中国名义 GDP](real_data_evidence/assets/cn_gdp.svg)

![欧元区 HICP 同比](real_data_evidence/assets/ea_hicp_yoy.svg)

![主要经济体名义 GDP 对比](real_data_evidence/assets/compare_gdp_2023.svg)

## 4. 可用性与实用性说明

网页的可用性体现在“查询条件输入、图表展示、JSON 输出、质量报告、错误提示”形成闭环。用户可以从示例卡片进入查询，也可以手动选择国家、指标、日期和频率。查询成功后，页面同步展示趋势图、最新值、元数据、质量校验结果和完整 JSON；查询失败时，错误信息会说明是参数问题还是上游接口临时不可用。

网页的实用性体现在三类使用场景：

- **研究人员**可以快速查询 GDP、CPI、利率、汇率等宏观指标，并导出 JSON 供后续分析。
- **参赛或汇报展示**可以用趋势图和横向对比图说明系统已经接通真实数据源，而不是静态样例。
- **AI Agent 或自动化脚本**可以通过 `/schema`、`/capabilities` 和 `/series` 自动发现能力、构造请求并解析结果。

## 5. 展示路线建议

建议演示顺序如下：

1. 打开首页，说明系统接入 7 个官方源、18 个标准指标和 33 条示例查询。
2. 点击“中国 GDP”，展示 World Bank 年度数据和质量报告。
3. 点击“美国 CPI”，展示 BLS 月度 CPI 同比，并说明派生指标会记录同比计算方法和基准月份。
4. 点击 OECD 美国 CPI 同比，展示同类指标可从不同官方源获取，用于跨源复核。
5. 打开“国家对比”或 `/compare`，展示 2023 年主要经济体 GDP 横向对比。
6. 打开 JSON 输出、`/schema` 和 `/capabilities`，说明系统可被程序和 Agent 调用。


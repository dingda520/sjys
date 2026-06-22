import argparse
import importlib.util
import json
import sys
import threading
import urllib.request
from pathlib import Path
from http.server import ThreadingHTTPServer


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

spec = importlib.util.spec_from_file_location("macro_datahub_service", PROJECT_DIR / "app.py")
app = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(app)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def test_static_contracts():
    assert_true(len(app.COUNTRIES) >= 8, "country dictionary should contain at least 8 entries")
    assert_true(len(app.INDICATORS) >= 18, "indicator dictionary should contain all source additions")
    assert_true(len(app.SAMPLE_QUERIES) >= 33, "sample queries should contain all source examples")

    capabilities = app.build_capabilities()
    implemented_sources = [item["source"] for item in capabilities["implemented_sources"]]
    for source in ["World Bank", "BLS", "Eurostat", "IMF", "OECD", "ECB", "BIS"]:
        assert_true(source in implemented_sources, f"capabilities should mark {source} as implemented")
    assert_true("/series" in [x["path"] for x in capabilities["endpoints"]], "capabilities should expose /series")
    assert_true("/visualization" in [x["path"] for x in capabilities["endpoints"]], "capabilities should expose /visualization")
    assert_true("/insight" in [x["path"] for x in capabilities["endpoints"]], "capabilities should expose /insight")
    assert_true("/compare" in [x["path"] for x in capabilities["endpoints"]], "capabilities should expose /compare")
    assert_true("/consistency" in [x["path"] for x in capabilities["endpoints"]], "capabilities should expose /consistency")
    assert_true("/search-indicators" in [x["path"] for x in capabilities["endpoints"]], "capabilities should expose /search-indicators")
    assert_true("/showcase" in [x["path"] for x in capabilities["endpoints"]], "capabilities should expose /showcase")
    assert_true("/evaluation" in [x["path"] for x in capabilities["endpoints"]], "capabilities should expose /evaluation")
    assert_true("/agent-tools" in [x["path"] for x in capabilities["endpoints"]], "capabilities should expose /agent-tools")
    assert_true("/error-catalog" in [x["path"] for x in capabilities["endpoints"]], "capabilities should expose /error-catalog")
    assert_true("/openapi-lite" in [x["path"] for x in capabilities["endpoints"]], "capabilities should expose /openapi-lite")
    assert_true(capabilities["agent_ready"] is True, "capabilities should mark service as agent ready")

    schema = app.build_response_schema()
    assert_true("request" in schema["top_level_fields"], "schema should describe request")
    assert_true("series" in schema["top_level_fields"], "schema should describe series")
    assert_true("quality_report" in schema["top_level_fields"], "schema should describe quality_report")
    assert_true("query_parameter_schema" in schema, "schema should describe query parameters")
    assert_true("eurostat_series" in schema["examples"], "schema should include Eurostat example")
    assert_true("imf_series" in schema["examples"], "schema should include IMF example")
    assert_true("oecd_series" in schema["examples"], "schema should include OECD example")
    assert_true("ecb_series" in schema["examples"], "schema should include ECB example")
    assert_true("bis_series" in schema["examples"], "schema should include BIS example")
    assert_true("consistency" in schema["examples"], "schema should include consistency example")
    assert_true("insight" in schema["examples"], "schema should include insight example")

    tools = app.build_agent_tools()
    tool_names = [tool["name"] for tool in tools["tools"]]
    assert_true("get_series" in tool_names, "agent tools should include get_series")
    assert_true("search_indicators" in tool_names, "agent tools should include search_indicators")
    assert_true("check_consistency" in tool_names, "agent tools should include check_consistency")
    assert_true("get_insight" in tool_names, "agent tools should include get_insight")

    errors = app.build_error_catalog()
    error_codes = [item["code"] for item in errors["errors"]]
    assert_true("validation_error" in error_codes, "error catalog should include validation_error")
    assert_true("source_request_failed" in error_codes, "error catalog should include source_request_failed")

    openapi = app.build_openapi_lite()
    assert_true("/series" in openapi["paths"], "openapi-lite should expose /series")
    assert_true("/consistency" in openapi["paths"], "openapi-lite should expose /consistency")
    assert_true("/insight" in openapi["paths"], "openapi-lite should expose /insight")
    assert_true(openapi["paths"]["/series"]["get"]["operationId"] == "get_series", "openapi-lite should map series operation")


def test_schema_models():
    from app.models import (
        DataLineage,
        Observation,
        QualityReport,
        QueryRequest,
        SeriesMetadata,
        SourceMetadata,
        StandardResponse,
    )

    source = SourceMetadata(
        organization="World Bank",
        dataset="World Development Indicators",
        source_series_code="NY.GDP.MKTP.CD",
        source_url="https://api.worldbank.org/",
        source="World Bank",
    )
    metadata = SeriesMetadata(
        series_id="CN.GDP_NOMINAL.A",
        indicator_code="GDP_NOMINAL",
        indicator_name_zh="名义 GDP",
        indicator_name_en="GDP, current US$",
        country_code="CN",
        country_name_zh="中国",
        country_name_en="China",
        frequency="A",
        unit="current US$",
        seasonal_adjustment="NSA",
        calculation="level",
        source=source,
        last_updated="2026-06-19",
    )
    response = StandardResponse(
        request=QueryRequest("CN", "GDP_NOMINAL", "2020", "2021", "A"),
        metadata=metadata,
        observations=[Observation(date="2021", value=100.0, unit="current US$", status="final")],
        quality_report=QualityReport(observation_count=1, unit_consistent=True, traceable_source=True, passed=True),
        lineage=DataLineage(
            provider="World Bank",
            dataset="World Development Indicators",
            api_url="https://api.worldbank.org/",
            retrieved_at="2026-06-19T00:00:00Z",
        ),
    )
    payload = response.to_dict()
    assert_true(payload["request"]["country"] == "CN", "schema request should serialize")
    assert_true(payload["metadata"]["source"]["organization"] == "World Bank", "source metadata should serialize")
    assert_true(payload["observations"][0]["date"] == "2021", "observations should serialize")
    assert_true(payload["quality_report"]["passed"] is True, "quality report should serialize")


def test_service_layer():
    from app.services import build_error_response, build_quality_report, standardize_series

    source = {
        "organization": "World Bank",
        "dataset": "World Development Indicators",
        "source_series_code": "NY.GDP.MKTP.CD",
    }
    quality = build_quality_report(
        [{"date": "2020", "value": 1.0}, {"date": "2021", "value": 2.0}],
        "A",
        "current US$",
        source,
    )
    assert_true(quality["passed"] is True, "service quality report should pass valid observations")

    error = build_error_response("US", "BAD", "2020", "2021", "A", "validation_error", "bad input")
    assert_true(error["lineage"] is None, "service error response should include lineage placeholder")
    assert_true(error["error"]["code"] == "validation_error", "service error response should preserve code")

    result = standardize_series(
        "CN",
        "GDP_NOMINAL",
        "2020",
        "2021",
        "A",
        [{"date": "2021", "value": 100.0, "status": "final"}],
        "https://api.worldbank.org/example",
        app.COUNTRIES,
        app.INDICATORS,
        app.SOURCE_MAPPINGS,
    )
    assert_true(result["series"]["series_id"] == "CN.GDP_NOMINAL.A", "service standardizer should build series_id")
    assert_true(result["lineage"]["provider"] == "World Bank", "service standardizer should build lineage")


def test_validation_errors():
    result = app.query_series("US", "CPI_YOY", "2020-01", "2020-12", "A")
    assert_true(result["series"] is None, "invalid frequency should not return a series")
    assert_true(result["error"]["code"] == "validation_error", "invalid frequency should return validation_error")

    result = app.query_series("CN", "CPI_YOY", "2020-01", "2020-12", "M")
    assert_true(result["series"] is None, "unsupported country scope should not return a series")
    assert_true(result["error"]["code"] == "validation_error", "unsupported scope should return validation_error")


def test_visualization_payload():
    result = app.standardize_series(
        "CN",
        "GDP_NOMINAL",
        "2020",
        "2021",
        "A",
        [
            {"date": "2020", "value": 100.0, "status": "final"},
            {"date": "2021", "value": 110.0, "status": "final"},
        ],
        "https://example.test/source",
    )
    payload = app.build_visualization_payload(result)
    assert_true(payload["error"] is None, "valid series should build visualization payload")
    assert_true(payload["chart"]["type"] == "line", "visualization should be a line chart")
    assert_true(payload["chart"]["xAxis"] == ["2020", "2021"], "xAxis should preserve dates")
    assert_true(payload["summary"]["latest_change"] == 10.0, "visualization should include latest change summary")
    assert_true(len(payload["table"]) == 2, "visualization should include table rows")
    assert_true(payload["lineage"]["provider"] == "World Bank", "visualization should preserve lineage")

    insight = app.build_insight_payload(result)
    assert_true(insight["error"] is None, "valid series should build insight payload")
    assert_true("report_paragraph" in insight["insight"], "insight should include report paragraph")
    assert_true("中国" in insight["insight"]["headline"], "insight headline should be localized")
    assert_true(len(insight["insight"]["bullets"]) >= 4, "insight should include presentation bullets")


def test_eurostat_parser_and_consistency():
    raw = {
        "id": ["freq", "geo", "time"],
        "size": [1, 1, 3],
        "dimension": {
            "time": {"category": {"index": {"2024-01": 0, "2024-02": 1, "2024-03": 2}}},
        },
        "value": {"0": 93.9, "1": 95.1, "2": 93.9},
        "status": {"1": "p"},
    }
    observations = app.parse_eurostat_observations(raw, "2024-01", "2024-03")
    assert_true(len(observations) == 3, "Eurostat parser should decode time/value observations")
    assert_true(observations[1]["status"] == "preliminary", "Eurostat parser should map status codes")

    consistency = app.build_consistency_payload()
    assert_true(consistency["summary"]["source_count"] >= 7, "consistency should cover all seven implemented sources")
    assert_true(consistency["summary"]["complete_indicator_count"] == consistency["summary"]["indicator_count"], "all indicators should have required metadata")
    assert_true(any(check["check"] == "Eurostat 新增指标覆盖" and check["passed"] for check in consistency["checks"]), "consistency should prove Eurostat additions")


def test_new_source_parsers():
    oecd_csv = "\n".join([
        "DATAFLOW,REF_AREA,FREQ,MEASURE,UNIT_MEASURE,ACTIVITY,ADJUSTMENT,TRANSFORMATION,TIME_PERIOD,OBS_VALUE,OBS_STATUS",
        "OECD.SDD.STES:DSD_KEI@DF_KEI(4.0),USA,M,CP,GR,_Z,_Z,GY,2024-01,3.1,A",
        "OECD.SDD.STES:DSD_KEI@DF_KEI(4.0),USA,M,CP,IX,_Z,_Z,_Z,2024-01,130.1,A",
    ])
    oecd_obs = app.parse_oecd_csv(oecd_csv, {"MEASURE": "CP", "UNIT_MEASURE": "GR", "TRANSFORMATION": "GY"}, "2024-01", "2024-03")
    assert_true(len(oecd_obs) == 1 and oecd_obs[0]["value"] == 3.1, "OECD parser should filter CSV rows")

    ecb_raw = {
        "structure": {"dimensions": {"observation": [{"values": [{"id": "2024-01"}, {"id": "2024-02"}]}]}},
        "dataSets": [{"series": {"0:0:0:0:0": {"observations": {"0": [1.09], "1": [1.08]}}}}],
    }
    ecb_obs = app.parse_ecb_jsondata(ecb_raw, "2024-01", "2024-02")
    assert_true(len(ecb_obs) == 2 and ecb_obs[0]["date"] == "2024-01", "ECB parser should decode JSON data")

    bis_xml = """<message:StructureSpecificData xmlns:message="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message"><message:DataSet><Series><Obs TIME_PERIOD="2024-01" OBS_VALUE="5.375" OBS_STATUS="A" /></Series></message:DataSet></message:StructureSpecificData>"""
    bis_obs = app.parse_bis_xml(bis_xml, "2024-01", "2024-03")
    assert_true(len(bis_obs) == 1 and bis_obs[0]["value"] == 5.375, "BIS parser should decode structure-specific XML")


def test_search_and_compare_payloads():
    search = app.search_indicators("gdp")
    assert_true(search["count"] >= 2, "GDP search should return multiple indicators")
    assert_true(any(item["indicator_code"] == "GDP_NOMINAL" for item in search["indicators"]), "GDP_NOMINAL should be searchable")
    eurostat = app.search_indicators("industrial")
    assert_true(any(item["indicator_code"] == "INDUSTRIAL_PRODUCTION" for item in eurostat["indicators"]), "Eurostat industrial production should be searchable")
    imf = app.search_indicators("imf")
    assert_true(any(item["indicator_code"] == "IMF_GDP_GROWTH" for item in imf["indicators"]), "IMF indicator should be searchable")

    compare = app.build_compare_payload("XX", "GDP_NOMINAL", "2023", "A")
    assert_true(compare["error"] is not None, "invalid compare request should return a structured error")
    assert_true(compare["errors"][0]["error"]["code"] == "validation_error", "invalid country should be reported")

    cache = app.build_cache_stats()
    assert_true("file_count" in cache, "cache stats should include file_count")

    evaluation = app.build_evaluation_payload()
    assert_true(len(evaluation["minimum_acceptance"]) >= 5, "evaluation should cover minimum acceptance requirements")
    assert_true(len(evaluation["scoring_alignment"]) == 5, "evaluation should cover five scoring dimensions")
    assert_true(evaluation["implemented_capabilities"]["sample_queries"] >= 20, "evaluation should prove sample query count")


def test_http_showcase_route():
    server = ThreadingHTTPServer(("127.0.0.1", 0), app.MacroHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/showcase", timeout=8) as resp:
            html = resp.read().decode("utf-8")
        assert_true("Macro DataHub 展示版" in html, "showcase page should render title")
        assert_true("seriesChart" in html, "showcase page should include series chart")
        assert_true("compareChart" in html, "showcase page should include compare chart")
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=8) as resp:
            main_html = resp.read().decode("utf-8")
        assert_true("评审看板" in main_html, "main page should include evaluation dashboard")
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/evaluation", timeout=8) as resp:
            evaluation = json.loads(resp.read().decode("utf-8"))
        assert_true(evaluation["error"] is None, "evaluation endpoint should return structured payload")
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/consistency", timeout=8) as resp:
            consistency = json.loads(resp.read().decode("utf-8"))
        assert_true(consistency["error"] is None, "consistency endpoint should return structured payload")
        assert_true(consistency["summary"]["source_count"] >= 7, "consistency endpoint should expose seven sources")
        for path in ["/agent-tools", "/error-catalog", "/openapi-lite", "/insight?country=XX&indicator_code=GDP_NOMINAL&start_date=2020&end_date=2021&frequency=A"]:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=8) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            assert_true(isinstance(payload, dict), f"{path} should return JSON object")
    finally:
        server.shutdown()
        server.server_close()


def test_online_queries():
    checks = [
        ("CN", "GDP_NOMINAL", "2020", "2021", "A"),
        ("US", "CPI_YOY", "2023-01", "2023-03", "M"),
        ("DE", "INDUSTRIAL_PRODUCTION", "2024-01", "2024-03", "M"),
        ("US", "IMF_GDP_GROWTH", "2020", "2024", "A"),
        ("US", "OECD_CPI_YOY", "2024-01", "2024-03", "M"),
        ("EA", "ECB_EUR_USD", "2024-01", "2024-03", "M"),
        ("US", "BIS_POLICY_RATE", "2024-01", "2024-03", "M"),
    ]
    results = []
    for query in checks:
        result = app.query_series(*query)
        results.append(
            {
                "query": query,
                "error": result.get("error"),
                "observations": len((result.get("series") or {}).get("observations", [])),
            }
        )
    print(json.dumps(results, ensure_ascii=False, indent=2))
    failed_required = [
        item for item in results
        if item["query"][1] != "CPI_YOY" and (item["error"] is not None or item["observations"] <= 0)
    ]
    assert_true(not failed_required, f"non-BLS online sources should return data: {failed_required}")
    bls = next(item for item in results if item["query"][1] == "CPI_YOY")
    assert_true(
        bls["observations"] > 0 or (bls["error"] or {}).get("code") == "source_request_failed",
        "BLS should either return data or expose a structured upstream timeout error",
    )


def main():
    parser = argparse.ArgumentParser(description="Macro DataHub smoke tests")
    parser.add_argument("--online", action="store_true", help="also test official online APIs")
    args = parser.parse_args()

    test_static_contracts()
    test_schema_models()
    test_service_layer()
    test_validation_errors()
    test_visualization_payload()
    test_eurostat_parser_and_consistency()
    test_new_source_parsers()
    test_search_and_compare_payloads()
    test_http_showcase_route()
    if args.online:
        test_online_queries()

    print("smoke tests passed")


if __name__ == "__main__":
    main()

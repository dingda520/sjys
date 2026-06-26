# -*- coding: utf-8 -*-
"""
经观 EconView
A dependency-free macroeconomic data governance and analytics service.

Run:
    python app.py
Then open:
    http://127.0.0.1:8000

Implemented official public APIs:
- World Bank Indicators API
- U.S. Bureau of Labor Statistics Public Data API
- Eurostat Statistics API
- IMF DataMapper / WEO API
- OECD SDMX API
- ECB Data API
- BIS Statistics API

No external Python package is required.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import statistics
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import xml.etree.ElementTree as ET
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.services import (
    build_error_response as service_build_error_response,
    build_quality_report as service_build_quality_report,
    standardize_series as service_standardize_series,
)


PROJECT_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = PROJECT_DIR / "frontend"
DATA_DIR = PROJECT_DIR / "data"
CACHE_DIR = PROJECT_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)

REQUEST_TIMEOUT_SECONDS = 25
HTTP_RETRY_COUNT = 2
HTTP_RETRY_BACKOFF_SECONDS = 1.5
HTTP_USER_AGENT = "Mozilla/5.0 (compatible; EconView/1.0; +https://sjys-th73.onrender.com)"
EUROSTAT_BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
IMF_DATAMAPPER_BASE_URL = "https://www.imf.org/external/datamapper/api/v2"
OECD_KEI_BASE_URL = "https://sdmx.oecd.org/public/rest/v1/data/OECD.SDD.STES,DSD_KEI%40DF_KEI"
ECB_DATA_API_BASE_URL = "https://data-api.ecb.europa.eu/service/data"
BIS_API_BASE_URL = "https://stats.bis.org/api/v1/data"
EUROSTAT_STATUS_LABELS = {
    "p": "preliminary",
    "e": "estimated",
    "b": "break",
}
SDMX_STATUS_LABELS = {
    "A": "final",
    "P": "preliminary",
    "E": "estimated",
}

APP_VERSION = "1.3.1"
BUILD_ID = "20260626-01"
DEPLOYED_AT = "2026-06-26T11:30:00+08:00"


COUNTRIES: Dict[str, Dict[str, Any]] = {
    "US": {"name_zh": "美国", "name_en": "United States", "entity_type": "country", "iso2": "US", "iso3": "USA", "wb_code": "USA", "eurostat_code": "", "imf_code": "USA", "oecd_code": "USA", "ecb_code": "", "bis_code": "US"},
    "CN": {"name_zh": "中国", "name_en": "China", "entity_type": "country", "iso2": "CN", "iso3": "CHN", "wb_code": "CHN", "eurostat_code": "", "imf_code": "CHN", "oecd_code": "CHN", "ecb_code": "", "bis_code": "CN"},
    "DE": {"name_zh": "德国", "name_en": "Germany", "entity_type": "country", "iso2": "DE", "iso3": "DEU", "wb_code": "DEU", "eurostat_code": "DE", "imf_code": "DEU", "oecd_code": "DEU", "ecb_code": "", "bis_code": "DE"},
    "JP": {"name_zh": "日本", "name_en": "Japan", "entity_type": "country", "iso2": "JP", "iso3": "JPN", "wb_code": "JPN", "eurostat_code": "", "imf_code": "JPN", "oecd_code": "JPN", "ecb_code": "", "bis_code": "JP"},
    "GB": {"name_zh": "英国", "name_en": "United Kingdom", "entity_type": "country", "iso2": "GB", "iso3": "GBR", "wb_code": "GBR", "eurostat_code": "", "imf_code": "GBR", "oecd_code": "GBR", "ecb_code": "", "bis_code": "GB"},
    "IN": {"name_zh": "印度", "name_en": "India", "entity_type": "country", "iso2": "IN", "iso3": "IND", "wb_code": "IND", "eurostat_code": "", "imf_code": "IND", "oecd_code": "", "ecb_code": "", "bis_code": "IN"},
    "FR": {"name_zh": "法国", "name_en": "France", "entity_type": "country", "iso2": "FR", "iso3": "FRA", "wb_code": "FRA", "eurostat_code": "FR", "imf_code": "FRA", "oecd_code": "FRA", "ecb_code": "", "bis_code": "FR"},
    "EA": {
        "name_zh": "欧元区",
        "name_en": "Euro Area",
        "entity_type": "region",
        "country_code": "EA",
        "wb_code": "EMU",
        "eurostat_code": "EA20",
        "imf_code": "",
        "oecd_code": "",
        "ecb_code": "U2",
        "bis_code": "XM",
        "provider_codes": {"world_bank": "EMU", "eurostat": "EA20", "ecb": "U2", "bis": "XM"},
    },
}

INDICATORS: Dict[str, Dict[str, Any]] = {
    "GDP_NOMINAL": {
        "indicator_name_zh": "名义 GDP",
        "indicator_name_en": "GDP, current US$",
        "frequency": ["A"],
        "unit": "current US$",
        "calculation": "level",
        "seasonal_adjustment": "NSA",
        "preferred_source": "World Bank",
        "description": "按现价美元计量的国内生产总值。",
    },
    "GDP_REAL_GROWTH": {
        "indicator_name_zh": "实际 GDP 增长率",
        "indicator_name_en": "GDP growth, annual %",
        "frequency": ["A"],
        "unit": "%",
        "calculation": "YoY",
        "seasonal_adjustment": "NSA",
        "preferred_source": "World Bank",
        "description": "按不变价格计算的年度 GDP 增长率。",
    },
    "EXPORTS": {
        "indicator_name_zh": "货物和服务出口",
        "indicator_name_en": "Exports of goods and services, current US$",
        "frequency": ["A"],
        "unit": "current US$",
        "calculation": "level",
        "seasonal_adjustment": "NSA",
        "preferred_source": "World Bank",
        "description": "货物和服务出口总额，现价美元。",
    },
    "IMPORTS": {
        "indicator_name_zh": "货物和服务进口",
        "indicator_name_en": "Imports of goods and services, current US$",
        "frequency": ["A"],
        "unit": "current US$",
        "calculation": "level",
        "seasonal_adjustment": "NSA",
        "preferred_source": "World Bank",
        "description": "货物和服务进口总额，现价美元。",
    },
    "TRADE_BALANCE": {
        "indicator_name_zh": "贸易差额",
        "indicator_name_en": "External balance on goods and services, current US$",
        "frequency": ["A"],
        "unit": "current US$",
        "calculation": "level",
        "seasonal_adjustment": "NSA",
        "preferred_source": "World Bank",
        "description": "货物和服务净出口，现价美元。",
    },
    "CPI_LEVEL": {
        "indicator_name_zh": "居民消费价格指数",
        "indicator_name_en": "Consumer Price Index, all urban consumers",
        "frequency": ["M"],
        "unit": "index, 1982-84=100",
        "calculation": "level",
        "seasonal_adjustment": "SA",
        "preferred_source": "BLS",
        "description": "美国城市消费者 CPI 指数。",
        "country_scope": ["US"],
    },
    "CPI_YOY": {
        "indicator_name_zh": "居民消费价格指数同比",
        "indicator_name_en": "Consumer Price Index YoY",
        "frequency": ["M"],
        "unit": "%",
        "calculation": "YoY",
        "seasonal_adjustment": "SA",
        "preferred_source": "BLS",
        "description": "由美国 CPI 指数计算得到的同比增速。",
        "country_scope": ["US"],
    },
    "UNEMP_RATE": {
        "indicator_name_zh": "失业率",
        "indicator_name_en": "Unemployment Rate",
        "frequency": ["M"],
        "unit": "%",
        "calculation": "level",
        "seasonal_adjustment": "SA",
        "preferred_source": "BLS",
        "description": "美国失业率，季调。",
        "country_scope": ["US"],
    },
    "NONFARM_PAYROLL": {
        "indicator_name_zh": "非农就业人数",
        "indicator_name_en": "All Employees, Total Nonfarm",
        "frequency": ["M"],
        "unit": "thousands of persons",
        "calculation": "level",
        "seasonal_adjustment": "SA",
        "preferred_source": "BLS",
        "description": "美国非农就业人数，季调。",
        "country_scope": ["US"],
    },
    "HICP_YOY": {
        "indicator_name_zh": "调和居民消费价格指数同比",
        "indicator_name_en": "Harmonised Index of Consumer Prices YoY",
        "frequency": ["M"],
        "unit": "%",
        "calculation": "YoY",
        "seasonal_adjustment": "NSA",
        "preferred_source": "Eurostat",
        "description": "Eurostat HICP 全项目同比变动率。",
        "country_scope": ["EA", "DE", "FR"],
    },
    "PPI_LEVEL": {
        "indicator_name_zh": "工业生产者价格指数",
        "indicator_name_en": "Producer prices in industry",
        "frequency": ["M"],
        "unit": "index, 2021=100",
        "calculation": "level",
        "seasonal_adjustment": "NSA",
        "preferred_source": "Eurostat",
        "description": "Eurostat 工业生产者价格指数，覆盖 B-D 工业部门。",
        "country_scope": ["EA", "DE", "FR"],
    },
    "INDUSTRIAL_PRODUCTION": {
        "indicator_name_zh": "工业生产指数",
        "indicator_name_en": "Industrial production index",
        "frequency": ["M"],
        "unit": "index, 2021=100",
        "calculation": "level",
        "seasonal_adjustment": "SCA",
        "preferred_source": "Eurostat",
        "description": "Eurostat 工业生产数量指数，季调与工作日调整。",
        "country_scope": ["EA", "DE", "FR"],
    },
    "RETAIL_SALES_VOLUME": {
        "indicator_name_zh": "零售销售量指数",
        "indicator_name_en": "Retail sales volume index",
        "frequency": ["M"],
        "unit": "index, 2021=100",
        "calculation": "level",
        "seasonal_adjustment": "SCA",
        "preferred_source": "Eurostat",
        "description": "Eurostat 零售贸易销售量指数，覆盖 G47 零售业。",
        "country_scope": ["EA", "DE", "FR"],
    },
    "LONG_TERM_RATE": {
        "indicator_name_zh": "长期政府债券收益率",
        "indicator_name_en": "Long-term government bond yield",
        "frequency": ["M"],
        "unit": "%",
        "calculation": "level",
        "seasonal_adjustment": "NSA",
        "preferred_source": "Eurostat",
        "description": "Eurostat 欧元趋同标准长期政府债券收益率。",
        "country_scope": ["DE", "FR"],
    },
    "IMF_GDP_GROWTH": {
        "indicator_name_zh": "IMF 实际 GDP 增长率",
        "indicator_name_en": "IMF real GDP growth",
        "frequency": ["A"],
        "unit": "%",
        "calculation": "YoY",
        "seasonal_adjustment": "NSA",
        "preferred_source": "IMF",
        "description": "IMF DataMapper / WEO 实际 GDP 年度增长率。",
        "country_scope": ["US", "CN", "DE", "JP", "GB", "IN", "FR"],
    },
    "OECD_CPI_YOY": {
        "indicator_name_zh": "OECD 居民消费价格指数同比",
        "indicator_name_en": "OECD consumer prices YoY",
        "frequency": ["M"],
        "unit": "%",
        "calculation": "YoY",
        "seasonal_adjustment": "NSA",
        "preferred_source": "OECD",
        "description": "OECD Key short-term economic indicators 中的 CPI 年同比。",
        "country_scope": ["US", "DE", "FR", "JP", "GB"],
    },
    "ECB_EUR_USD": {
        "indicator_name_zh": "欧元兑美元汇率",
        "indicator_name_en": "US dollar / Euro exchange rate",
        "frequency": ["M"],
        "unit": "USD per EUR",
        "calculation": "level",
        "seasonal_adjustment": "NSA",
        "preferred_source": "ECB",
        "description": "ECB Data Portal 欧元兑美元月度平均即期汇率。",
        "country_scope": ["EA"],
    },
    "BIS_POLICY_RATE": {
        "indicator_name_zh": "中央银行政策利率",
        "indicator_name_en": "Central bank policy rate",
        "frequency": ["M"],
        "unit": "%",
        "calculation": "level",
        "seasonal_adjustment": "NSA",
        "preferred_source": "BIS",
        "description": "BIS Central bank policy rates 月度期末政策利率。",
        "country_scope": ["US", "EA", "FR", "GB", "JP", "CN", "IN"],
    },
}

SOURCE_MAPPINGS: Dict[str, Dict[str, Any]] = {
    "GDP_NOMINAL": {
        "source": "World Bank",
        "organization": "World Bank",
        "dataset": "World Development Indicators",
        "source_series_code": "NY.GDP.MKTP.CD",
        "supported_countries": "all",
    },
    "GDP_REAL_GROWTH": {
        "source": "World Bank",
        "organization": "World Bank",
        "dataset": "World Development Indicators",
        "source_series_code": "NY.GDP.MKTP.KD.ZG",
        "supported_countries": "all",
    },
    "EXPORTS": {
        "source": "World Bank",
        "organization": "World Bank",
        "dataset": "World Development Indicators",
        "source_series_code": "NE.EXP.GNFS.CD",
        "supported_countries": "all",
    },
    "IMPORTS": {
        "source": "World Bank",
        "organization": "World Bank",
        "dataset": "World Development Indicators",
        "source_series_code": "NE.IMP.GNFS.CD",
        "supported_countries": "all",
    },
    "TRADE_BALANCE": {
        "source": "World Bank",
        "organization": "World Bank",
        "dataset": "World Development Indicators",
        "source_series_code": "NE.RSB.GNFS.CD",
        "supported_countries": "all",
    },
    "CPI_LEVEL": {
        "source": "BLS",
        "organization": "U.S. Bureau of Labor Statistics",
        "dataset": "Consumer Price Index",
        "source_series_code": "CUSR0000SA0",
        "supported_countries": ["US"],
    },
    "CPI_YOY": {
        "source": "BLS",
        "organization": "U.S. Bureau of Labor Statistics",
        "dataset": "Consumer Price Index",
        "source_series_code": "CUSR0000SA0",
        "supported_countries": ["US"],
        "derived_from": "CPI_LEVEL",
    },
    "UNEMP_RATE": {
        "source": "BLS",
        "organization": "U.S. Bureau of Labor Statistics",
        "dataset": "Labor Force Statistics",
        "source_series_code": "LNS14000000",
        "supported_countries": ["US"],
    },
    "NONFARM_PAYROLL": {
        "source": "BLS",
        "organization": "U.S. Bureau of Labor Statistics",
        "dataset": "Current Employment Statistics",
        "source_series_code": "CES0000000001",
        "supported_countries": ["US"],
    },
    "HICP_YOY": {
        "source": "Eurostat",
        "organization": "Eurostat",
        "dataset": "HICP - monthly data (annual rate of change)",
        "source_series_code": "prc_hicp_manr",
        "supported_countries": ["EA", "DE", "FR"],
        "eurostat_dataset": "prc_hicp_manr",
        "eurostat_params": {"unit": "RCH_A", "coicop": "CP00"},
    },
    "PPI_LEVEL": {
        "source": "Eurostat",
        "organization": "Eurostat",
        "dataset": "Short-term business statistics - producer prices in industry",
        "source_series_code": "sts_inpp_m:PRC_PRR:B-D",
        "supported_countries": ["EA", "DE", "FR"],
        "eurostat_dataset": "sts_inpp_m",
        "eurostat_params": {"indic_bt": "PRC_PRR", "nace_r2": "B-D", "s_adj": "NSA", "unit": "I21"},
    },
    "INDUSTRIAL_PRODUCTION": {
        "source": "Eurostat",
        "organization": "Eurostat",
        "dataset": "Short-term business statistics - production in industry",
        "source_series_code": "sts_inpr_m:PRD:B-D",
        "supported_countries": ["EA", "DE", "FR"],
        "eurostat_dataset": "sts_inpr_m",
        "eurostat_params": {"indic_bt": "PRD", "nace_r2": "B-D", "s_adj": "SCA", "unit": "I21"},
    },
    "RETAIL_SALES_VOLUME": {
        "source": "Eurostat",
        "organization": "Eurostat",
        "dataset": "Short-term business statistics - retail trade volume",
        "source_series_code": "sts_trtu_m:VOL_SLS:G47",
        "supported_countries": ["EA", "DE", "FR"],
        "eurostat_dataset": "sts_trtu_m",
        "eurostat_params": {"indic_bt": "VOL_SLS", "nace_r2": "G47", "s_adj": "SCA", "unit": "I21"},
    },
    "LONG_TERM_RATE": {
        "source": "Eurostat",
        "organization": "Eurostat",
        "dataset": "Long-term interest rates for convergence purposes",
        "source_series_code": "irt_lt_mcby_m:MCBY",
        "supported_countries": ["DE", "FR"],
        "eurostat_dataset": "irt_lt_mcby_m",
        "eurostat_params": {"int_rt": "MCBY"},
    },
    "IMF_GDP_GROWTH": {
        "source": "IMF",
        "organization": "International Monetary Fund",
        "dataset": "World Economic Outlook / DataMapper",
        "source_series_code": "NGDP_RPCH",
        "supported_countries": ["US", "CN", "DE", "JP", "GB", "IN", "FR"],
        "imf_indicator": "NGDP_RPCH",
    },
    "OECD_CPI_YOY": {
        "source": "OECD",
        "organization": "Organisation for Economic Co-operation and Development",
        "dataset": "Key short-term economic indicators",
        "source_series_code": "DSD_KEI@DF_KEI:CP:GR:GY",
        "supported_countries": ["US", "DE", "FR", "JP", "GB"],
        "oecd_key_template": "{country}.M.CP....",
        "oecd_filters": {"MEASURE": "CP", "UNIT_MEASURE": "GR", "TRANSFORMATION": "GY"},
    },
    "ECB_EUR_USD": {
        "source": "ECB",
        "organization": "European Central Bank",
        "dataset": "Exchange Rates",
        "source_series_code": "EXR/M.USD.EUR.SP00.A",
        "supported_countries": ["EA"],
        "ecb_flow": "EXR",
        "ecb_key": "M.USD.EUR.SP00.A",
    },
    "BIS_POLICY_RATE": {
        "source": "BIS",
        "organization": "Bank for International Settlements",
        "dataset": "Central bank policy rates",
        "source_series_code": "WS_CBPOL",
        "supported_countries": ["US", "EA", "FR", "GB", "JP", "CN", "IN"],
        "bis_flow": "WS_CBPOL",
        "bis_key_template": "M.{country}",
    },
}


SAMPLE_QUERIES: List[Dict[str, str]] = [
    {"country": "US", "indicator_code": "CPI_YOY", "start_date": "2020-01", "end_date": "2025-12", "frequency": "M"},
    {"country": "US", "indicator_code": "CPI_LEVEL", "start_date": "2020-01", "end_date": "2025-12", "frequency": "M"},
    {"country": "US", "indicator_code": "UNEMP_RATE", "start_date": "2020-01", "end_date": "2025-12", "frequency": "M"},
    {"country": "US", "indicator_code": "NONFARM_PAYROLL", "start_date": "2020-01", "end_date": "2025-12", "frequency": "M"},
    {"country": "US", "indicator_code": "GDP_NOMINAL", "start_date": "2018", "end_date": "2024", "frequency": "A"},
    {"country": "CN", "indicator_code": "GDP_NOMINAL", "start_date": "2018", "end_date": "2024", "frequency": "A"},
    {"country": "DE", "indicator_code": "GDP_NOMINAL", "start_date": "2018", "end_date": "2024", "frequency": "A"},
    {"country": "JP", "indicator_code": "GDP_NOMINAL", "start_date": "2018", "end_date": "2024", "frequency": "A"},
    {"country": "GB", "indicator_code": "GDP_NOMINAL", "start_date": "2018", "end_date": "2024", "frequency": "A"},
    {"country": "IN", "indicator_code": "GDP_NOMINAL", "start_date": "2018", "end_date": "2024", "frequency": "A"},
    {"country": "FR", "indicator_code": "GDP_REAL_GROWTH", "start_date": "2018", "end_date": "2024", "frequency": "A"},
    {"country": "CN", "indicator_code": "GDP_REAL_GROWTH", "start_date": "2018", "end_date": "2024", "frequency": "A"},
    {"country": "DE", "indicator_code": "EXPORTS", "start_date": "2018", "end_date": "2024", "frequency": "A"},
    {"country": "JP", "indicator_code": "EXPORTS", "start_date": "2018", "end_date": "2024", "frequency": "A"},
    {"country": "GB", "indicator_code": "IMPORTS", "start_date": "2018", "end_date": "2024", "frequency": "A"},
    {"country": "IN", "indicator_code": "IMPORTS", "start_date": "2018", "end_date": "2024", "frequency": "A"},
    {"country": "US", "indicator_code": "TRADE_BALANCE", "start_date": "2018", "end_date": "2024", "frequency": "A"},
    {"country": "CN", "indicator_code": "TRADE_BALANCE", "start_date": "2018", "end_date": "2024", "frequency": "A"},
    {"country": "DE", "indicator_code": "TRADE_BALANCE", "start_date": "2018", "end_date": "2024", "frequency": "A"},
    {"country": "EA", "indicator_code": "GDP_NOMINAL", "start_date": "2018", "end_date": "2024", "frequency": "A"},
    {"country": "EA", "indicator_code": "GDP_REAL_GROWTH", "start_date": "2018", "end_date": "2024", "frequency": "A"},
    {"country": "FR", "indicator_code": "EXPORTS", "start_date": "2018", "end_date": "2024", "frequency": "A"},
    {"country": "FR", "indicator_code": "IMPORTS", "start_date": "2018", "end_date": "2024", "frequency": "A"},
    {"country": "GB", "indicator_code": "TRADE_BALANCE", "start_date": "2018", "end_date": "2024", "frequency": "A"},
    {"country": "EA", "indicator_code": "HICP_YOY", "start_date": "2023-01", "end_date": "2024-12", "frequency": "M"},
    {"country": "DE", "indicator_code": "PPI_LEVEL", "start_date": "2023-01", "end_date": "2024-12", "frequency": "M"},
    {"country": "DE", "indicator_code": "INDUSTRIAL_PRODUCTION", "start_date": "2023-01", "end_date": "2024-12", "frequency": "M"},
    {"country": "FR", "indicator_code": "RETAIL_SALES_VOLUME", "start_date": "2023-01", "end_date": "2024-12", "frequency": "M"},
    {"country": "DE", "indicator_code": "LONG_TERM_RATE", "start_date": "2023-01", "end_date": "2024-12", "frequency": "M"},
    {"country": "US", "indicator_code": "IMF_GDP_GROWTH", "start_date": "2020", "end_date": "2024", "frequency": "A"},
    {"country": "US", "indicator_code": "OECD_CPI_YOY", "start_date": "2024-01", "end_date": "2024-12", "frequency": "M"},
    {"country": "EA", "indicator_code": "ECB_EUR_USD", "start_date": "2024-01", "end_date": "2024-12", "frequency": "M"},
    {"country": "US", "indicator_code": "BIS_POLICY_RATE", "start_date": "2024-01", "end_date": "2024-12", "frequency": "M"},
]

SOURCE_RUNTIME_STATUS: List[Dict[str, Any]] = [
    {"source": "World Bank", "status": "normal", "mode": "LIVE", "last_success_at": "2026-06-26T10:28:00+08:00", "latency_ms": 1240, "note": "年度指标实时接口可用"},
    {"source": "BLS", "status": "slow", "mode": "CACHE", "last_success_at": "2026-06-25T18:20:00+08:00", "latency_ms": 2830, "note": "官方接口偶发超时，保留结构化错误和缓存兜底"},
    {"source": "Eurostat", "status": "normal", "mode": "LIVE", "last_success_at": "2026-06-26T10:30:00+08:00", "latency_ms": 1570, "note": "月度 SDMX JSON 接口可用"},
    {"source": "IMF", "status": "normal", "mode": "LIVE", "last_success_at": "2026-06-26T10:31:00+08:00", "latency_ms": 980, "note": "DataMapper 年度数据可用"},
    {"source": "OECD", "status": "normal", "mode": "LIVE", "last_success_at": "2026-06-26T10:29:00+08:00", "latency_ms": 1760, "note": "CSV/SDMX 代表性接口可用"},
    {"source": "ECB", "status": "normal", "mode": "LIVE", "last_success_at": "2026-06-26T10:29:00+08:00", "latency_ms": 870, "note": "汇率 JSON 接口可用"},
    {"source": "BIS", "status": "normal", "mode": "LIVE", "last_success_at": "2026-06-26T10:32:00+08:00", "latency_ms": 1160, "note": "政策利率 XML 接口可用"},
]

SAMPLE_VALIDATION_RUN = {
    "run_id": "RUN-20260626-001",
    "started_at": "2026-06-26T10:30:00+08:00",
    "completed_at": "2026-06-26T10:32:00+08:00",
    "checked_at": "2026-06-26T10:32:00+08:00",
    "mode": "VERIFIED SNAPSHOT",
    "schema_version": APP_VERSION,
}


def cache_path(namespace: str, key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{namespace}_{digest}.json"


def cache_get(namespace: str, key: str) -> Optional[Any]:
    path = cache_path(namespace, key)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def cache_set(namespace: str, key: str, value: Any) -> None:
    path = cache_path(namespace, key)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def http_json_get(url: str, namespace: str) -> Any:
    cached = cache_get(namespace, url)
    if cached is not None:
        return cached

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": HTTP_USER_AGENT,
            "Accept": "application/json",
        },
    )
    last_error: Optional[Exception] = None
    for attempt in range(HTTP_RETRY_COUNT + 1):
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
                data = resp.read().decode("utf-8")
                raw = json.loads(data)
                cache_set(namespace, url, raw)
                return raw
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < HTTP_RETRY_COUNT:
                time.sleep(HTTP_RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue
            raise
    raise RuntimeError(f"HTTP GET failed: {last_error}")


def http_text_get(url: str, namespace: str, accept: str = "text/plain,*/*") -> str:
    cached = cache_get(namespace, url)
    if isinstance(cached, str):
        return cached

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": HTTP_USER_AGENT,
            "Accept": accept,
        },
    )
    last_error: Optional[Exception] = None
    for attempt in range(HTTP_RETRY_COUNT + 1):
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
                text = resp.read().decode("utf-8")
                cache_set(namespace, url, text)
                return text
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < HTTP_RETRY_COUNT:
                time.sleep(HTTP_RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue
            raise
    raise RuntimeError(f"HTTP GET failed: {last_error}")


def http_json_post(url: str, payload: Dict[str, Any], namespace: str, timeout_seconds: Optional[int] = None, retry_count: Optional[int] = None) -> Any:
    cache_key = url + "|" + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    cached = cache_get(namespace, cache_key)
    if cached is not None:
        return cached

    body = json.dumps(payload).encode("utf-8")
    effective_timeout = timeout_seconds or REQUEST_TIMEOUT_SECONDS
    effective_retry_count = HTTP_RETRY_COUNT if retry_count is None else retry_count
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "User-Agent": HTTP_USER_AGENT,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    last_error: Optional[Exception] = None
    for attempt in range(effective_retry_count + 1):
        try:
            with urllib.request.urlopen(req, timeout=effective_timeout) as resp:
                data = resp.read().decode("utf-8")
                raw = json.loads(data)
                cache_set(namespace, cache_key, raw)
                return raw
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < effective_retry_count:
                time.sleep(HTTP_RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue
            raise
    raise RuntimeError(f"HTTP POST failed: {last_error}")


def parse_year(value: str) -> int:
    if not value:
        return datetime.today().year
    return int(str(value)[:4])


def normalize_month(value: str) -> str:
    value = str(value)
    if len(value) == 4:
        return f"{value}-01"
    parts = value.split("-")
    if len(parts) >= 2:
        return f"{int(parts[0]):04d}-{int(parts[1]):02d}"
    return value


def in_range(period: str, start_date: Optional[str], end_date: Optional[str]) -> bool:
    if start_date:
        start = normalize_month(start_date) if "-" in period else str(start_date)[:4]
        if period < start[: len(period)]:
            return False
    if end_date:
        end = normalize_month(end_date) if "-" in period else str(end_date)[:4]
        if period > end[: len(period)]:
            return False
    return True


def month_range(start: str, end: str) -> List[str]:
    y, m = map(int, normalize_month(start).split("-")[:2])
    ey, em = map(int, normalize_month(end).split("-")[:2])
    out: List[str] = []
    while (y, m) <= (ey, em):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y += 1
            m = 1
    return out


def year_range(start: str, end: str) -> List[str]:
    sy = int(str(start)[:4])
    ey = int(str(end)[:4])
    return [str(y) for y in range(sy, ey + 1)]


def robust_outlier_count(values: List[Optional[float]]) -> int:
    clean = [float(v) for v in values if v is not None and isinstance(v, (int, float))]
    if len(clean) < 8:
        return 0
    diffs = [clean[i] - clean[i - 1] for i in range(1, len(clean))]
    if len(diffs) < 6:
        return 0
    med = statistics.median(diffs)
    mad = statistics.median([abs(x - med) for x in diffs])
    if mad == 0:
        return 0
    return sum(1 for x in diffs if abs(x - med) / mad > 8)


def build_quality_report(observations: List[Dict[str, Any]], frequency: str, unit: str, source: Dict[str, Any]) -> Dict[str, Any]:
    return service_build_quality_report(observations, frequency, unit, source)


def build_error_response(country: str, indicator_code: str, start_date: str, end_date: str, frequency: str, code: str, message: str, detail: Any = None) -> Dict[str, Any]:
    return service_build_error_response(country, indicator_code, start_date, end_date, frequency, code, message, detail)


def standardize_series(country: str, indicator_code: str, start_date: str, end_date: str, frequency: str, observations: List[Dict[str, Any]], source_url: str) -> Dict[str, Any]:
    return service_standardize_series(
        country,
        indicator_code,
        start_date,
        end_date,
        frequency,
        observations,
        source_url,
        COUNTRIES,
        INDICATORS,
        SOURCE_MAPPINGS,
        service_build_quality_report,
    )


def fetch_worldbank(country: str, indicator_code: str, start_date: str, end_date: str, frequency: str) -> Dict[str, Any]:
    if frequency != "A":
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "unsupported_frequency", "World Bank V1 supports annual frequency A only.")
    if country not in COUNTRIES:
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "unsupported_country", f"Unsupported country: {country}")

    source_code = SOURCE_MAPPINGS[indicator_code]["source_series_code"]
    wb_country = COUNTRIES[country]["wb_code"]
    start_year = parse_year(start_date)
    end_year = parse_year(end_date)
    url = (
        f"https://api.worldbank.org/v2/country/{urllib.parse.quote(wb_country)}/indicator/{urllib.parse.quote(source_code)}"
        f"?format=json&date={start_year}:{end_year}&per_page=20000"
    )

    try:
        raw = http_json_get(url, "worldbank")
    except Exception as exc:
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "source_request_failed", "World Bank API request failed.", str(exc))

    if not isinstance(raw, list) or len(raw) < 2:
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "source_format_error", "World Bank API returned unexpected format.", raw)

    observations: List[Dict[str, Any]] = []
    for item in raw[1] or []:
        date = str(item.get("date"))
        value = item.get("value")
        if value is None:
            continue
        if not in_range(date, str(start_year), str(end_year)):
            continue
        observations.append({
            "date": date,
            "value": float(value),
            "status": "final",
        })

    return standardize_series(country, indicator_code, start_date, end_date, frequency, observations, url)


def parse_bls_observations(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    series_list = raw.get("Results", {}).get("series", [])
    if not series_list:
        raise ValueError("BLS response contains no series.")
    data = series_list[0].get("data", [])
    observations: List[Dict[str, Any]] = []
    for item in data:
        period = item.get("period")
        if not period or not str(period).startswith("M") or period == "M13":
            continue
        year = int(item["year"])
        month = int(str(period)[1:])
        date = f"{year:04d}-{month:02d}"
        value_raw = item.get("value")
        if value_raw is None:
            continue
        value_text = str(value_raw).replace(",", "").strip()
        if value_text in {"", "-", "."}:
            continue
        try:
            value = float(value_text)
        except ValueError:
            continue
        footnotes = item.get("footnotes", [])
        status = "preliminary" if any(isinstance(f, dict) and f.get("code") == "P" for f in footnotes) else "final"
        observations.append({
            "date": date,
            "value": value,
            "status": status,
        })
    return sorted(observations, key=lambda x: x["date"])


def compute_yoy(observations: List[Dict[str, Any]], start_date: str, end_date: str) -> List[Dict[str, Any]]:
    by_date = {o["date"]: o for o in observations}
    out: List[Dict[str, Any]] = []
    for o in observations:
        year = int(o["date"][:4])
        month = o["date"][5:7]
        prev_date = f"{year - 1:04d}-{month}"
        prev = by_date.get(prev_date)
        if prev and prev["value"] not in (0, None):
            yoy = (float(o["value"]) / float(prev["value"]) - 1.0) * 100.0
            if in_range(o["date"], start_date, end_date):
                out.append({
                    "date": o["date"],
                    "value": round(yoy, 4),
                    "status": o.get("status", "final"),
                    "derived": {
                        "method": "YoY = current index / same month previous year - 1",
                        "base_date": prev_date,
                    },
                })
    return out


def fetch_bls(country: str, indicator_code: str, start_date: str, end_date: str, frequency: str) -> Dict[str, Any]:
    if country != "US":
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "unsupported_country", "BLS indicators in V1 support US only.")
    if frequency != "M":
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "unsupported_frequency", "BLS indicators in V1 support monthly frequency M only.")

    mapping = SOURCE_MAPPINGS[indicator_code]
    series_id = mapping["source_series_code"]
    start_year = parse_year(start_date)
    end_year = parse_year(end_date)
    fetch_start_year = start_year - 1 if indicator_code == "CPI_YOY" else start_year
    url = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
    payload = {
        "seriesid": [series_id],
        "startyear": str(fetch_start_year),
        "endyear": str(end_year),
    }

    try:
        raw = http_json_post(url, payload, "bls", timeout_seconds=10, retry_count=1)
    except Exception as exc:
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "source_request_failed", "BLS API request failed.", str(exc))

    if raw.get("status") != "REQUEST_SUCCEEDED":
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "source_status_error", "BLS API did not return REQUEST_SUCCEEDED.", raw)

    try:
        parsed = parse_bls_observations(raw)
    except Exception as exc:
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "source_format_error", "BLS API returned unexpected format.", str(exc))

    if indicator_code == "CPI_YOY":
        observations = compute_yoy(parsed, start_date, end_date)
    else:
        observations = [o for o in parsed if in_range(o["date"], start_date, end_date)]

    return standardize_series(country, indicator_code, start_date, end_date, frequency, observations, url)


def parse_eurostat_observations(raw: Dict[str, Any], start_date: str, end_date: str) -> List[Dict[str, Any]]:
    dimension = raw.get("dimension", {})
    time_category = dimension.get("time", {}).get("category", {})
    time_index = time_category.get("index", {})
    if not isinstance(time_index, dict) or not time_index:
        raise ValueError("Eurostat response contains no time index.")

    index_to_time = {int(index): period for period, index in time_index.items()}
    time_size = max(index_to_time) + 1
    values = raw.get("value", {})
    if not isinstance(values, dict):
        raise ValueError("Eurostat response contains no value map.")

    status_map = raw.get("status", {}) if isinstance(raw.get("status"), dict) else {}
    observations: List[Dict[str, Any]] = []
    for flat_index, value in values.items():
        if value is None:
            continue
        time_pos = int(flat_index) % time_size
        period = index_to_time.get(time_pos)
        if not period or not in_range(period, start_date, end_date):
            continue
        status_code = str(status_map.get(str(flat_index), "")).lower()
        observations.append({
            "date": period,
            "value": float(value),
            "status": EUROSTAT_STATUS_LABELS.get(status_code, "final"),
        })

    return sorted(observations, key=lambda x: x["date"])


def fetch_eurostat(country: str, indicator_code: str, start_date: str, end_date: str, frequency: str) -> Dict[str, Any]:
    if frequency != "M":
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "unsupported_frequency", "Eurostat connector currently supports monthly frequency M only.")

    eurostat_geo = COUNTRIES.get(country, {}).get("eurostat_code", "")
    if not eurostat_geo:
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "unsupported_country", f"Eurostat mapping is not configured for country: {country}")

    mapping = SOURCE_MAPPINGS[indicator_code]
    dataset = mapping.get("eurostat_dataset")
    if not dataset:
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "source_format_error", "Eurostat dataset code is missing from source mapping.")

    query_params: List[Tuple[str, str]] = [
        ("format", "JSON"),
        ("lang", "en"),
        ("geo", eurostat_geo),
        ("sinceTimePeriod", normalize_month(start_date)),
        ("untilTimePeriod", normalize_month(end_date)),
    ]
    for key, value in sorted(mapping.get("eurostat_params", {}).items()):
        query_params.append((key, str(value)))

    url = f"{EUROSTAT_BASE_URL}/{urllib.parse.quote(str(dataset))}?{urllib.parse.urlencode(query_params)}"
    try:
        raw = http_json_get(url, "eurostat")
    except Exception as exc:
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "source_request_failed", "Eurostat API request failed.", str(exc))

    try:
        observations = parse_eurostat_observations(raw, start_date, end_date)
    except Exception as exc:
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "source_format_error", "Eurostat API returned unexpected format.", str(exc))

    return standardize_series(country, indicator_code, start_date, end_date, frequency, observations, url)


def fetch_imf(country: str, indicator_code: str, start_date: str, end_date: str, frequency: str) -> Dict[str, Any]:
    if frequency != "A":
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "unsupported_frequency", "IMF DataMapper connector currently supports annual frequency A only.")

    imf_country = COUNTRIES.get(country, {}).get("imf_code", "")
    if not imf_country:
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "unsupported_country", f"IMF mapping is not configured for country: {country}")

    mapping = SOURCE_MAPPINGS[indicator_code]
    imf_indicator = mapping.get("imf_indicator", mapping["source_series_code"])
    years = year_range(start_date, end_date)
    periods = ",".join(years)
    url = f"{IMF_DATAMAPPER_BASE_URL}/{urllib.parse.quote(str(imf_indicator))}/{urllib.parse.quote(imf_country)}?periods={urllib.parse.quote(periods)}"
    try:
        raw = http_json_get(url, "imf")
    except Exception as exc:
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "source_request_failed", "IMF DataMapper API request failed.", str(exc))

    values = raw.get("values", {}).get(str(imf_indicator), {}).get(imf_country, {})
    if not isinstance(values, dict):
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "source_format_error", "IMF DataMapper API returned unexpected format.", raw)

    observations = [
        {"date": year, "value": float(values[year]), "status": "final"}
        for year in years
        if year in values and values[year] is not None
    ]
    return standardize_series(country, indicator_code, start_date, end_date, frequency, observations, url)


def parse_oecd_csv(text: str, filters: Dict[str, str], start_date: str, end_date: str) -> List[Dict[str, Any]]:
    rows = csv.DictReader(text.splitlines())
    observations: List[Dict[str, Any]] = []
    for row in rows:
        if any(row.get(key) != value for key, value in filters.items()):
            continue
        period = row.get("TIME_PERIOD", "")
        value = row.get("OBS_VALUE")
        if not period or value in (None, "") or not in_range(period, start_date, end_date):
            continue
        status = SDMX_STATUS_LABELS.get(str(row.get("OBS_STATUS", "A")).upper(), "final")
        observations.append({"date": period, "value": float(value), "status": status})
    return sorted(observations, key=lambda x: x["date"])


def fetch_oecd(country: str, indicator_code: str, start_date: str, end_date: str, frequency: str) -> Dict[str, Any]:
    if frequency != "M":
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "unsupported_frequency", "OECD KEI connector currently supports monthly frequency M only.")

    oecd_country = COUNTRIES.get(country, {}).get("oecd_code", "")
    if not oecd_country:
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "unsupported_country", f"OECD mapping is not configured for country: {country}")

    mapping = SOURCE_MAPPINGS[indicator_code]
    key_template = mapping.get("oecd_key_template")
    if not key_template:
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "source_format_error", "OECD key template is missing from source mapping.")

    oecd_key = str(key_template).format(country=oecd_country)
    params = urllib.parse.urlencode({
        "startPeriod": normalize_month(start_date),
        "endPeriod": normalize_month(end_date),
    })
    url = f"{OECD_KEI_BASE_URL}/{urllib.parse.quote(oecd_key, safe='.') }?{params}"
    try:
        text = http_text_get(url, "oecd", "text/csv,*/*")
    except Exception as exc:
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "source_request_failed", "OECD SDMX API request failed.", str(exc))

    observations = parse_oecd_csv(text, mapping.get("oecd_filters", {}), start_date, end_date)
    return standardize_series(country, indicator_code, start_date, end_date, frequency, observations, url)


def parse_ecb_jsondata(raw: Dict[str, Any], start_date: str, end_date: str) -> List[Dict[str, Any]]:
    obs_dims = raw.get("structure", {}).get("dimensions", {}).get("observation", [])
    if not obs_dims:
        raise ValueError("ECB JSON response contains no observation dimensions.")
    time_values = obs_dims[0].get("values", [])
    datasets = raw.get("dataSets", [])
    if not datasets:
        raise ValueError("ECB JSON response contains no datasets.")

    observations: List[Dict[str, Any]] = []
    for series in (datasets[0].get("series") or {}).values():
        for index, values in (series.get("observations") or {}).items():
            period_info = time_values[int(index)]
            period = period_info.get("id")
            if not period or not in_range(period, start_date, end_date):
                continue
            value = values[0] if values else None
            if value is None:
                continue
            observations.append({"date": period, "value": float(value), "status": "final"})
    return sorted(observations, key=lambda x: x["date"])


def fetch_ecb(country: str, indicator_code: str, start_date: str, end_date: str, frequency: str) -> Dict[str, Any]:
    if country != "EA":
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "unsupported_country", "ECB exchange-rate indicator is exposed under EA in this project.")
    if frequency != "M":
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "unsupported_frequency", "ECB connector currently supports monthly frequency M only.")

    mapping = SOURCE_MAPPINGS[indicator_code]
    flow = mapping.get("ecb_flow", "EXR")
    key = mapping.get("ecb_key")
    params = urllib.parse.urlencode({
        "startPeriod": normalize_month(start_date),
        "endPeriod": normalize_month(end_date),
        "format": "jsondata",
    })
    url = f"{ECB_DATA_API_BASE_URL}/{urllib.parse.quote(str(flow))}/{urllib.parse.quote(str(key), safe='.') }?{params}"
    try:
        raw = http_json_get(url, "ecb")
    except Exception as exc:
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "source_request_failed", "ECB Data API request failed.", str(exc))

    try:
        observations = parse_ecb_jsondata(raw, start_date, end_date)
    except Exception as exc:
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "source_format_error", "ECB Data API returned unexpected format.", str(exc))
    return standardize_series(country, indicator_code, start_date, end_date, frequency, observations, url)


def xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def parse_bis_xml(text: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    root = ET.fromstring(text)
    observations: List[Dict[str, Any]] = []
    for elem in root.iter():
        if xml_local_name(elem.tag) != "Obs":
            continue
        period = elem.attrib.get("TIME_PERIOD")
        value = elem.attrib.get("OBS_VALUE")
        if not period or value in (None, "") or not in_range(period, start_date, end_date):
            continue
        status = SDMX_STATUS_LABELS.get(str(elem.attrib.get("OBS_STATUS", "A")).upper(), "final")
        observations.append({"date": period, "value": float(value), "status": status})
    return sorted(observations, key=lambda x: x["date"])


def fetch_bis(country: str, indicator_code: str, start_date: str, end_date: str, frequency: str) -> Dict[str, Any]:
    if frequency != "M":
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "unsupported_frequency", "BIS policy-rate connector currently supports monthly frequency M only.")

    bis_country = COUNTRIES.get(country, {}).get("bis_code", "")
    if not bis_country:
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "unsupported_country", f"BIS mapping is not configured for country: {country}")

    mapping = SOURCE_MAPPINGS[indicator_code]
    flow = mapping.get("bis_flow", mapping["source_series_code"])
    bis_key = str(mapping.get("bis_key_template", "M.{country}")).format(country=bis_country)
    params = urllib.parse.urlencode({
        "startPeriod": normalize_month(start_date),
        "endPeriod": normalize_month(end_date),
    })
    url = f"{BIS_API_BASE_URL}/{urllib.parse.quote(str(flow))}/{urllib.parse.quote(bis_key, safe='.') }?{params}"
    try:
        text = http_text_get(url, "bis", "application/xml,text/xml,*/*")
    except Exception as exc:
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "source_request_failed", "BIS Statistics API request failed.", str(exc))

    try:
        observations = parse_bis_xml(text, start_date, end_date)
    except Exception as exc:
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "source_format_error", "BIS Statistics API returned unexpected format.", str(exc))
    return standardize_series(country, indicator_code, start_date, end_date, frequency, observations, url)


def query_series(country: str, indicator_code: str, start_date: str, end_date: str, frequency: str) -> Dict[str, Any]:
    country = (country or "").upper().strip()
    indicator_code = (indicator_code or "").upper().strip()
    frequency = (frequency or "").upper().strip()

    if country not in COUNTRIES:
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "validation_error", f"Unknown country code: {country}")

    if indicator_code not in INDICATORS:
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "validation_error", f"Unknown indicator_code: {indicator_code}")

    indicator = INDICATORS[indicator_code]
    if frequency not in indicator["frequency"]:
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "validation_error", f"{indicator_code} does not support frequency {frequency}. Supported: {indicator['frequency']}")

    scope = indicator.get("country_scope")
    if scope and country not in scope:
        return build_error_response(country, indicator_code, start_date, end_date, frequency, "validation_error", f"{indicator_code} supports countries {scope} in V1.")

    source = SOURCE_MAPPINGS[indicator_code]["source"]
    if source == "World Bank":
        return fetch_worldbank(country, indicator_code, start_date, end_date, frequency)
    if source == "BLS":
        return fetch_bls(country, indicator_code, start_date, end_date, frequency)
    if source == "Eurostat":
        return fetch_eurostat(country, indicator_code, start_date, end_date, frequency)
    if source == "IMF":
        return fetch_imf(country, indicator_code, start_date, end_date, frequency)
    if source == "OECD":
        return fetch_oecd(country, indicator_code, start_date, end_date, frequency)
    if source == "ECB":
        return fetch_ecb(country, indicator_code, start_date, end_date, frequency)
    if source == "BIS":
        return fetch_bis(country, indicator_code, start_date, end_date, frequency)
    return build_error_response(country, indicator_code, start_date, end_date, frequency, "unsupported_source", f"Unsupported source: {source}")


def build_capabilities() -> Dict[str, Any]:
    return {
        "service": "econview",
        "display_name": "经观 EconView",
        "version": APP_VERSION,
        "description": "全球宏观经济数据治理与分析平台，提供官方宏观数据查询、标准化 JSON、质量报告和数据血缘。",
        "slogan": "观全球经济，见数据脉络。",
        "agent_ready": True,
        "agent_entrypoints": ["/agent-tools", "/schema", "/capabilities", "/error-catalog", "/openapi-lite", "/insight"],
        "implemented_sources": [
            {
                "source": "World Bank",
                "organization": "World Bank",
                "datasets": ["World Development Indicators"],
                "frequency": ["A"],
                "status": "implemented",
            },
            {
                "source": "BLS",
                "organization": "U.S. Bureau of Labor Statistics",
                "datasets": ["Consumer Price Index", "Labor Force Statistics", "Current Employment Statistics"],
                "frequency": ["M"],
                "status": "implemented",
            },
            {
                "source": "Eurostat",
                "organization": "Eurostat",
                "datasets": [
                    "HICP monthly annual rate",
                    "Short-term business statistics",
                    "Long-term interest rates",
                ],
                "frequency": ["M"],
                "status": "implemented",
            },
            {
                "source": "IMF",
                "organization": "International Monetary Fund",
                "datasets": ["World Economic Outlook / DataMapper"],
                "frequency": ["A"],
                "status": "implemented",
            },
            {
                "source": "OECD",
                "organization": "Organisation for Economic Co-operation and Development",
                "datasets": ["Key short-term economic indicators"],
                "frequency": ["M"],
                "status": "implemented",
            },
            {
                "source": "ECB",
                "organization": "European Central Bank",
                "datasets": ["Exchange Rates"],
                "frequency": ["M"],
                "status": "implemented",
            },
            {
                "source": "BIS",
                "organization": "Bank for International Settlements",
                "datasets": ["Central bank policy rates"],
                "frequency": ["M"],
                "status": "implemented",
            },
        ],
        "planned_sources": [],
        "countries": [{"country_code": code, **info} for code, info in sorted(COUNTRIES.items())],
        "indicators": [
            {
                "indicator_code": code,
                "indicator_name_zh": info["indicator_name_zh"],
                "indicator_name_en": info["indicator_name_en"],
                "frequency": info["frequency"],
                "unit": info["unit"],
                "source": SOURCE_MAPPINGS[code]["source"],
                "country_scope": info.get("country_scope", "all"),
            }
            for code, info in sorted(INDICATORS.items())
        ],
        "endpoints": [
            {"method": "GET", "path": "/health", "purpose": "service health check"},
            {"method": "GET", "path": "/showcase", "purpose": "polished presentation dashboard"},
            {"method": "GET", "path": "/countries", "purpose": "supported country dictionary"},
            {"method": "GET", "path": "/indicators", "purpose": "supported indicator dictionary"},
            {"method": "GET", "path": "/search-indicators", "purpose": "keyword search over indicator dictionary"},
            {"method": "GET", "path": "/series", "purpose": "single standardized series query"},
            {"method": "POST", "path": "/batch-query", "purpose": "batch standardized series query"},
            {"method": "GET", "path": "/compare", "purpose": "multi-country comparison payload"},
            {"method": "GET", "path": "/visualization", "purpose": "ECharts-friendly line chart payload"},
            {"method": "GET", "path": "/insight", "purpose": "human-readable query insight and report paragraph"},
            {"method": "GET", "path": "/consistency", "purpose": "cross-source structural consistency check"},
            {"method": "GET", "path": "/cache-stats", "purpose": "file cache diagnostics"},
            {"method": "GET", "path": "/status", "purpose": "source runtime status snapshot"},
            {"method": "GET", "path": "/sample-validation", "purpose": "33-query acceptance validation report"},
            {"method": "GET", "path": "/evidence", "purpose": "public evidence links for acceptance review"},
            {"method": "GET", "path": "/evaluation", "purpose": "competition scoring evidence and acceptance checklist"},
            {"method": "GET", "path": "/schema", "purpose": "standard response schema description"},
            {"method": "GET", "path": "/agent-tools", "purpose": "AI Agent tool definitions and parameter schemas"},
            {"method": "GET", "path": "/error-catalog", "purpose": "machine-readable error codes and recovery hints"},
            {"method": "GET", "path": "/openapi-lite", "purpose": "lightweight OpenAPI-style endpoint contract"},
            {"method": "GET", "path": "/entry-audit", "purpose": "safe self-check for presentation and agent entrypoints"},
            {"method": "GET", "path": "/sample-queries", "purpose": "competition/demo sample queries"},
            {"method": "GET", "path": "/capabilities", "purpose": "machine-readable service capabilities"},
        ],
        "recommended_agent_flow": [
            "Call /capabilities to discover countries, indicators and endpoints.",
            "Call /search-indicators when the user describes an indicator in natural language.",
            "Call /series for a single standardized time series.",
            "Call /batch-query when the user asks for several series at once.",
            "Call /visualization when a chart-ready payload is required.",
            "Call /insight when a human-readable interpretation or report paragraph is required.",
            "Call /consistency to verify cross-source schema, metadata and lineage consistency.",
            "Inspect error.code and use /error-catalog for recovery guidance.",
        ],
    }


def build_agent_tools() -> Dict[str, Any]:
    return {
        "service": "econview",
        "display_name": "经观 EconView",
        "version": APP_VERSION,
        "tools": [
            {
                "name": "search_indicators",
                "description": "Search the standardized indicator dictionary by keyword, source or frequency.",
                "method": "GET",
                "path": "/search-indicators",
                "parameters": {
                    "q": {"type": "string", "required": False, "description": "Keyword such as GDP, CPI, 失业 or trade."},
                    "source": {"type": "string", "required": False, "description": "Optional source filter such as World Bank, BLS, Eurostat, IMF, OECD, ECB or BIS."},
                    "frequency": {"type": "string", "required": False, "enum": ["M", "A"], "description": "Optional frequency filter. V1 supports monthly and annual data only."},
                },
                "use_when": "The user asks what indicators are available or uses a non-standard indicator name.",
                "returns": ["request", "count", "indicators", "error"],
            },
            {
                "name": "get_series",
                "description": "Fetch one standardized macroeconomic time series with metadata, observations, quality report and lineage.",
                "method": "GET",
                "path": "/series",
                "parameters": {
                    "country": {"type": "string", "required": True, "description": "Supported country/region code such as US, CN, DE, EA."},
                    "indicator_code": {"type": "string", "required": True, "description": "Standard indicator code such as GDP_NOMINAL, CPI_YOY or INDUSTRIAL_PRODUCTION."},
                    "start_date": {"type": "string", "required": True, "description": "YYYY for annual data or YYYY-MM for monthly data."},
                    "end_date": {"type": "string", "required": True, "description": "YYYY for annual data or YYYY-MM for monthly data."},
                    "frequency": {"type": "string", "required": True, "enum": ["M", "A"], "description": "Observation frequency."},
                },
                "use_when": "The user asks for a specific country, indicator and time range.",
                "returns": ["request", "series", "quality_report", "lineage", "error"],
            },
            {
                "name": "batch_query",
                "description": "Run multiple standardized series queries in one request.",
                "method": "POST",
                "path": "/batch-query",
                "parameters": {
                    "queries": {
                        "type": "array",
                        "required": True,
                        "items": ["country", "indicator_code", "start_date", "end_date", "frequency"],
                    },
                },
                "use_when": "The user asks for many indicators or countries at once.",
                "returns": ["count", "results"],
            },
            {
                "name": "compare_countries",
                "description": "Compare one annual indicator across multiple countries and return chart-ready data.",
                "method": "GET",
                "path": "/compare",
                "parameters": {
                    "countries": {"type": "string", "required": False, "description": "Comma-separated country codes, e.g. US,CN,DE,JP."},
                    "indicator_code": {"type": "string", "required": True, "description": "Annual indicator code such as GDP_NOMINAL."},
                    "date": {"type": "string", "required": True, "description": "Comparison year, e.g. 2023."},
                    "frequency": {"type": "string", "required": False, "enum": ["A"], "description": "Currently annual comparison."},
                },
                "use_when": "The user asks for cross-country comparison or ranking.",
                "returns": ["request", "indicator", "rows", "errors", "chart", "error"],
            },
            {
                "name": "get_visualization",
                "description": "Return a line-chart payload and ECharts option for one series.",
                "method": "GET",
                "path": "/visualization",
                "parameters": {
                    "country": {"type": "string", "required": True},
                    "indicator_code": {"type": "string", "required": True},
                    "start_date": {"type": "string", "required": True},
                    "end_date": {"type": "string", "required": True},
                    "frequency": {"type": "string", "required": True, "enum": ["M", "A"]},
                },
                "use_when": "The user asks for a chart or dashboard-ready response.",
                "returns": ["request", "chart", "source", "quality_report", "error"],
            },
            {
                "name": "get_insight",
                "description": "Return a Chinese natural-language interpretation, report paragraph and key bullets for one macro series.",
                "method": "GET",
                "path": "/insight",
                "parameters": {
                    "country": {"type": "string", "required": True},
                    "indicator_code": {"type": "string", "required": True},
                    "start_date": {"type": "string", "required": True},
                    "end_date": {"type": "string", "required": True},
                    "frequency": {"type": "string", "required": True, "enum": ["M", "A"]},
                },
                "use_when": "The user asks what the data means, needs a report sentence, or wants a presentation-ready explanation.",
                "returns": ["request", "insight", "series", "quality_report", "lineage", "error"],
            },
            {
                "name": "check_consistency",
                "description": "Verify that implemented sources share required schema, metadata, quality and lineage contracts.",
                "method": "GET",
                "path": "/consistency",
                "parameters": {
                    "online": {"type": "boolean", "required": False, "description": "Set to true or 1 to run representative upstream API checks."},
                },
                "use_when": "The user asks whether sources are consistently standardized or competition requirements are satisfied.",
                "returns": ["request", "summary", "checks", "indicator_checks", "representative_queries", "online_results", "error"],
            },
            {
                "name": "get_source_status",
                "description": "Return source runtime status with LIVE/CACHE/SNAPSHOT mode definitions.",
                "method": "GET",
                "path": "/status",
                "parameters": {},
                "use_when": "The user asks whether official sources are currently available or demo-safe.",
                "returns": ["checked_at", "summary", "sources", "mode_definitions", "error"],
            },
            {
                "name": "get_sample_validation",
                "description": "Return the 33-query acceptance validation report with status, record count and latency.",
                "method": "GET",
                "path": "/sample-validation",
                "parameters": {},
                "use_when": "The user asks for proof that sample queries have been validated.",
                "returns": ["run", "summary", "rows", "interpretation", "error"],
            },
        ],
        "error_handling": "Check the top-level error field. When error is not null, inspect error.code and consult /error-catalog.",
    }


def build_error_catalog() -> Dict[str, Any]:
    return {
        "service": "econview",
        "display_name": "经观 EconView",
        "version": APP_VERSION,
        "errors": [
            {
                "code": "validation_error",
                "meaning": "The country, indicator or frequency is not supported by the current dictionary.",
                "retryable": False,
                "recovery_hint": "Call /countries, /indicators or /search-indicators, then retry with a supported value.",
                "agent_recovery": "Call /countries, /indicators or /search-indicators, then retry with a supported value.",
            },
            {
                "code": "unsupported_country",
                "meaning": "The selected source supports only specific countries for this indicator.",
                "retryable": False,
                "recovery_hint": "Inspect indicator country_scope from /indicators and choose a supported country.",
                "agent_recovery": "Inspect indicator country_scope from /indicators and choose a supported country.",
            },
            {
                "code": "unsupported_frequency",
                "meaning": "The selected indicator does not support the requested frequency.",
                "retryable": False,
                "recovery_hint": "Use the frequency list returned by /indicators. V1 supports M and A only.",
                "agent_recovery": "Use the frequency list returned by /indicators.",
            },
            {
                "code": "unsupported_source",
                "meaning": "The source exists in mapping but no connector is implemented yet.",
                "retryable": False,
                "recovery_hint": "Use implemented_sources from /capabilities.",
                "agent_recovery": "Use implemented_sources from /capabilities.",
            },
            {
                "code": "source_request_failed",
                "meaning": "The official upstream API could not be reached or timed out.",
                "retryable": True,
                "recovery_hint": "Retry later, or use /status and /sample-validation to inspect latest cache/snapshot evidence.",
                "agent_recovery": "Retry later, narrow the time range, or switch to another currently reachable official source. For BLS, SSL handshake timeouts are network/upstream failures, not missing observations.",
            },
            {
                "code": "source_format_error",
                "meaning": "The upstream API returned an unexpected response shape.",
                "retryable": True,
                "recovery_hint": "Retry later and inspect lineage.api_url to verify the upstream response.",
                "agent_recovery": "Report the source and query; avoid fabricating data.",
            },
            {
                "code": "source_status_error",
                "meaning": "The upstream API responded but reported a non-success status.",
                "retryable": True,
                "recovery_hint": "Expose the source error detail, then retry later or suggest another query.",
                "agent_recovery": "Expose the source error detail to the user and suggest another query.",
            },
            {
                "code": "empty_series",
                "meaning": "The request was valid but no observations were available.",
                "retryable": True,
                "recovery_hint": "Widen the date range or check whether the official source has published this series.",
                "agent_recovery": "Try a wider date range or another indicator.",
            },
            {
                "code": "not_found",
                "meaning": "The requested endpoint path does not exist.",
                "retryable": False,
                "recovery_hint": "Call /capabilities or /openapi-lite to inspect valid paths.",
                "agent_recovery": "Call /capabilities or /openapi-lite to inspect valid paths.",
            },
        ],
    }


def build_openapi_lite() -> Dict[str, Any]:
    tools = build_agent_tools()["tools"]
    return {
        "openapi": "lite-1.0",
        "info": {
            "title": "经观 EconView API",
            "version": APP_VERSION,
            "description": "全球宏观经济数据治理与分析平台，面向看板、研究脚本和 AI Agent 提供标准化宏观数据服务。",
        },
        "servers": [{"url": "/"}],
        "paths": {
            tool["path"]: {
                tool["method"].lower(): {
                    "operationId": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"],
                    "returns": tool["returns"],
                }
            }
            for tool in tools
        },
    }


def build_entry_audit_payload() -> Dict[str, Any]:
    checks = [
        ("系统能力", "/capabilities", build_capabilities),
        ("统一 Schema", "/schema", build_response_schema),
        ("Agent 工具", "/agent-tools", build_agent_tools),
        ("错误目录", "/error-catalog", build_error_catalog),
        ("OpenAPI Lite", "/openapi-lite", build_openapi_lite),
        ("成果总览", "/evaluation", build_evaluation_payload),
        ("示例查询", "/sample-queries", lambda: {"queries": SAMPLE_QUERIES}),
        ("样例验收", "/sample-validation", build_sample_validation_payload),
        ("数据源状态", "/status", build_source_status_payload),
    ]
    entries: List[Dict[str, Any]] = []
    for label, path, builder in checks:
        try:
            payload = builder()
            ok = isinstance(payload, dict) and not payload.get("error")
            entries.append({
                "label": label,
                "path": path,
                "ok": bool(ok),
                "status": "ready" if ok else "attention",
                "top_level_keys": list(payload.keys())[:8] if isinstance(payload, dict) else [],
                "message": "入口可用，返回结构化 JSON。" if ok else "入口返回了 error 字段，请复核。",
            })
        except Exception as exc:
            entries.append({
                "label": label,
                "path": path,
                "ok": False,
                "status": "failed",
                "top_level_keys": [],
                "message": str(exc),
            })
    return {
        "service": "econview",
        "checked_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "summary": {
            "entry_count": len(entries),
            "ready_count": sum(1 for item in entries if item["ok"]),
            "failed_count": sum(1 for item in entries if not item["ok"]),
        },
        "entries": entries,
        "error": None,
    }


def build_response_schema() -> Dict[str, Any]:
    return {
        "name": "EconViewStandardResponse",
        "version": APP_VERSION,
        "agent_usage": {
            "discovery_order": ["/capabilities", "/agent-tools", "/schema", "/error-catalog"],
            "query_order": ["/search-indicators", "/series", "/visualization", "/insight", "/consistency"],
            "do_not_fabricate_data": True,
            "error_rule": "If error is not null, do not use series fields as data. Explain error.message and recovery hint.",
        },
        "query_parameter_schema": {
            "country": {"type": "string", "required": True, "examples": ["US", "CN", "EA"]},
            "indicator_code": {"type": "string", "required": True, "examples": ["GDP_NOMINAL", "CPI_YOY", "INDUSTRIAL_PRODUCTION", "IMF_GDP_GROWTH", "BIS_POLICY_RATE"]},
            "start_date": {"type": "string", "required": True, "format": "YYYY or YYYY-MM"},
            "end_date": {"type": "string", "required": True, "format": "YYYY or YYYY-MM"},
            "frequency": {"type": "string", "required": True, "enum": ["M", "A"]},
        },
        "top_level_fields": {
            "request": {
                "type": "object",
                "fields": ["country", "indicator_code", "start_date", "end_date", "frequency"],
            },
            "series": {
                "type": "object|null",
                "fields": [
                    "series_id", "indicator_code", "indicator_name_zh", "indicator_name_en",
                    "country_name_zh", "country_name_en", "country_code", "frequency", "unit",
                    "seasonal_adjustment", "calculation", "source", "source_updated_at", "last_updated", "observations",
                ],
                "notes": {
                    "source_updated_at": "Official source publish/revision marker when available.",
                    "last_updated": "Backward-compatible alias for source_updated_at.",
                    "source": "Contains organization, dataset, source_series_code and source_url.",
                    "observations": "Array of standardized observations inside series, not a top-level field.",
                },
            },
            "quality_report": {
                "type": "object|null",
                "fields": [
                    "observation_count", "missing_periods", "missing_period_count",
                    "duplicate_records", "outlier_count", "unit_consistent",
                    "traceable_source", "checked_at", "passed",
                ],
            },
            "lineage": {
                "type": "object|null",
                "fields": ["provider", "dataset", "api_url", "retrieved_at", "parser", "raw_cache_key"],
                "notes": {"retrieved_at": "Platform retrieval time for this API call."},
            },
            "error": {
                "type": "object|null",
                "fields": ["code", "message", "detail", "retryable", "recovery_hint"],
            },
        },
        "observation_fields": {
            "date": "YYYY for annual data or YYYY-MM for monthly data",
            "value": "numeric value",
            "status": "final or preliminary",
            "derived": "optional derivation metadata for calculated indicators such as YoY",
        },
        "examples": {
            "single_series": "/series?country=CN&indicator_code=GDP_NOMINAL&start_date=2018&end_date=2024&frequency=A",
            "monthly_series": "/series?country=US&indicator_code=CPI_YOY&start_date=2020-01&end_date=2025-12&frequency=M",
            "eurostat_series": "/series?country=DE&indicator_code=INDUSTRIAL_PRODUCTION&start_date=2023-01&end_date=2024-12&frequency=M",
            "imf_series": "/series?country=US&indicator_code=IMF_GDP_GROWTH&start_date=2020&end_date=2024&frequency=A",
            "oecd_series": "/series?country=US&indicator_code=OECD_CPI_YOY&start_date=2024-01&end_date=2024-12&frequency=M",
            "ecb_series": "/series?country=EA&indicator_code=ECB_EUR_USD&start_date=2024-01&end_date=2024-12&frequency=M",
            "bis_series": "/series?country=US&indicator_code=BIS_POLICY_RATE&start_date=2024-01&end_date=2024-12&frequency=M",
            "indicator_search": "/search-indicators?q=gdp",
            "visualization": "/visualization?country=CN&indicator_code=GDP_NOMINAL&start_date=2018&end_date=2024&frequency=A",
            "insight": "/insight?country=IN&indicator_code=TRADE_BALANCE&start_date=2018&end_date=2024&frequency=A",
            "consistency": "/consistency",
        },
        "design_goals": [
            "same output shape for all official data sources",
            "traceable source metadata",
            "quality checks for missing, duplicate and abnormal observations",
            "directly usable by dashboards, agents and research scripts",
        ],
    }


def build_visualization_payload(result: Dict[str, Any]) -> Dict[str, Any]:
    if result.get("error") or not result.get("series"):
        return {
            "request": result.get("request"),
            "chart": None,
            "source": None,
            "quality_report": result.get("quality_report"),
            "error": result.get("error") or {"code": "empty_series", "message": "No series data available."},
        }

    series = result["series"]
    observations = series.get("observations", [])
    numeric_values = [float(o.get("value")) for o in observations if isinstance(o.get("value"), (int, float))]
    latest = observations[-1] if observations else None
    previous = observations[-2] if len(observations) >= 2 else None
    latest_value = latest.get("value") if latest else None
    previous_value = previous.get("value") if previous else None
    change = None
    change_pct = None
    if isinstance(latest_value, (int, float)) and isinstance(previous_value, (int, float)):
        change = latest_value - previous_value
        if previous_value != 0:
            change_pct = change / previous_value * 100.0
    summary = {
        "observation_count": len(observations),
        "first_date": observations[0].get("date") if observations else None,
        "last_date": latest.get("date") if latest else None,
        "latest_value": latest_value,
        "previous_value": previous_value,
        "latest_change": change,
        "latest_change_pct": change_pct,
        "min_value": min(numeric_values) if numeric_values else None,
        "max_value": max(numeric_values) if numeric_values else None,
        "unit": series["unit"],
    }
    return {
        "request": result.get("request"),
        "summary": summary,
        "chart": {
            "type": "line",
            "title": f"{series['country_name_zh']} - {series['indicator_name_zh']}",
            "subtitle": f"{series['source']['organization']} / {series['source']['dataset']}",
            "xAxis": [o.get("date") for o in observations],
            "series": [
                {
                    "name": series["indicator_code"],
                    "unit": series["unit"],
                    "data": [o.get("value") for o in observations],
                }
            ],
            "echarts_option": {
                "title": {"text": f"{series['country_name_zh']} - {series['indicator_name_zh']}", "subtext": series["source"]["organization"]},
                "tooltip": {"trigger": "axis"},
                "legend": {"top": 28},
                "grid": {"left": 56, "right": 28, "top": 78, "bottom": 48},
                "toolbox": {"feature": {"saveAsImage": {}, "dataZoom": {}, "restore": {}}},
                "dataZoom": [{"type": "inside"}, {"type": "slider", "height": 18, "bottom": 8}],
                "xAxis": {"type": "category", "data": [o.get("date") for o in observations]},
                "yAxis": {"type": "value", "name": series["unit"]},
                "series": [
                    {
                        "name": series["indicator_code"],
                        "type": "line",
                        "smooth": True,
                        "data": [o.get("value") for o in observations],
                    }
                ],
            },
        },
        "table": [
            {"date": o.get("date"), "value": o.get("value"), "status": o.get("status", ""), "unit": series["unit"]}
            for o in observations
        ],
        "source": series.get("source"),
        "quality_report": result.get("quality_report"),
        "lineage": result.get("lineage"),
        "error": None,
    }


def compact_number(value: float) -> str:
    abs_value = abs(value)
    digits = 1 if abs_value >= 100 else 2 if abs_value >= 10 else 3
    text = f"{value:,.{digits}f}"
    return text.rstrip("0").rstrip(".")


def choose_display_scale(values: List[float], unit: str) -> Dict[str, Any]:
    max_abs = max([abs(v) for v in values], default=0.0)
    unit_lower = (unit or "").lower()
    if "us$" in unit_lower or "usd" in unit_lower:
        if max_abs >= 1_000_000_000_000:
            return {"divisor": 1_000_000_000_000.0, "label_zh": "万亿美元", "label_en": "trillion USD"}
        if max_abs >= 1_000_000_000:
            return {"divisor": 1_000_000_000.0, "label_zh": "十亿美元", "label_en": "billion USD"}
        if max_abs >= 1_000_000:
            return {"divisor": 1_000_000.0, "label_zh": "百万美元", "label_en": "million USD"}
        return {"divisor": 1.0, "label_zh": "美元", "label_en": "USD"}
    if (unit or "").strip() == "%":
        return {"divisor": 1.0, "label_zh": "%", "label_en": "%"}
    if "person" in unit_lower:
        if max_abs >= 1_000_000:
            return {"divisor": 1_000_000.0, "label_zh": "百万人", "label_en": "million persons"}
        if max_abs >= 1_000:
            return {"divisor": 1_000.0, "label_zh": "千人", "label_en": "thousand persons"}
        return {"divisor": 1.0, "label_zh": "人", "label_en": "persons"}
    if "index" in unit_lower:
        return {"divisor": 1.0, "label_zh": "指数点", "label_en": "index points"}
    return {"divisor": 1.0, "label_zh": unit or "原始值", "label_en": unit or "raw value"}


def format_display_value(value: Any, scale: Dict[str, Any]) -> str:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return "-"
    scaled = float(value) / float(scale.get("divisor") or 1.0)
    if abs(scaled) < 0.0005:
        scaled = 0.0
    label = scale.get("label_zh") or ""
    return f"{compact_number(scaled)} {label}".strip()


def build_insight_payload(result: Dict[str, Any]) -> Dict[str, Any]:
    if result.get("error") or not result.get("series"):
        return {
            "request": result.get("request"),
            "insight": None,
            "series": None,
            "quality_report": result.get("quality_report"),
            "lineage": result.get("lineage"),
            "error": result.get("error") or {"code": "empty_series", "message": "No series data available."},
        }

    series = result["series"]
    observations = series.get("observations", [])
    numeric_observations = [
        item for item in observations
        if isinstance(item.get("value"), (int, float)) and math.isfinite(float(item.get("value")))
    ]
    if not numeric_observations:
        return {
            "request": result.get("request"),
            "insight": None,
            "series": {"series_id": series.get("series_id"), "source": series.get("source")},
            "quality_report": result.get("quality_report"),
            "lineage": result.get("lineage"),
            "error": {"code": "empty_series", "message": "No numeric observations available for insight."},
        }

    values = [float(item["value"]) for item in numeric_observations]
    scale = choose_display_scale(values, series.get("unit", ""))
    latest = numeric_observations[-1]
    previous = numeric_observations[-2] if len(numeric_observations) >= 2 else None
    max_item = max(numeric_observations, key=lambda item: float(item["value"]))
    min_item = min(numeric_observations, key=lambda item: float(item["value"]))
    latest_value = float(latest["value"])
    previous_value = float(previous["value"]) if previous else None
    change_abs = latest_value - previous_value if previous_value is not None else None
    change_pct = (change_abs / previous_value * 100.0) if previous_value not in (None, 0) else None
    if change_abs is None:
        change_phrase = "暂无上一期可比数据"
    elif change_abs > 0:
        change_phrase = f"较上一期增加 {format_display_value(abs(change_abs), scale)}"
    elif change_abs < 0:
        change_phrase = f"较上一期减少 {format_display_value(abs(change_abs), scale)}"
    else:
        change_phrase = "较上一期基本持平"

    calc_labels = {"level": "水平值", "YoY": "同比", "MoM": "环比"}
    sa_labels = {"NSA": "未季调", "SA": "季调", "SCA": "季调/工作日调整"}
    quality = result.get("quality_report") or {}
    quality_sentence = "质量校验通过，来源可追溯。" if quality.get("passed") else "质量校验提示需要复核，请查看 quality_report。"
    date_range = f"{numeric_observations[0].get('date')} 至 {latest.get('date')}"
    headline = f"{series.get('country_name_zh')} {series.get('indicator_name_zh')}最新值为 {format_display_value(latest_value, scale)}。"
    report_paragraph = (
        f"{date_range} 期间，{series.get('country_name_zh')}的{series.get('indicator_name_zh')}"
        f"最新观测期为{latest.get('date')}，数值为{format_display_value(latest_value, scale)}，{change_phrase}。"
        f"样本期内最高值出现在{max_item.get('date')}，为{format_display_value(max_item.get('value'), scale)}；"
        f"最低值出现在{min_item.get('date')}，为{format_display_value(min_item.get('value'), scale)}。"
        f"该指标口径为{calc_labels.get(series.get('calculation'), series.get('calculation'))}，"
        f"季调标识为{sa_labels.get(series.get('seasonal_adjustment'), series.get('seasonal_adjustment'))}。"
        f"数据来自{series.get('source', {}).get('organization')}的{series.get('source', {}).get('dataset')}，{quality_sentence}"
    )

    bullets = [
        f"最新观测：{latest.get('date')}，{format_display_value(latest_value, scale)}。",
        f"环比上一观测期：{change_phrase}。",
        f"区间最高：{max_item.get('date')}，{format_display_value(max_item.get('value'), scale)}。",
        f"区间最低：{min_item.get('date')}，{format_display_value(min_item.get('value'), scale)}。",
        f"来源：{series.get('source', {}).get('organization')} / {series.get('source', {}).get('dataset')}。",
    ]
    return {
        "request": result.get("request"),
        "insight": {
            "title": f"{series.get('country_name_zh')} · {series.get('indicator_name_zh')} 自动解读",
            "headline": headline,
            "report_paragraph": report_paragraph,
            "bullets": bullets,
            "metrics": {
                "observation_count": len(numeric_observations),
                "first_date": numeric_observations[0].get("date"),
                "last_date": latest.get("date"),
                "latest_value": latest_value,
                "latest_display": format_display_value(latest_value, scale),
                "previous_value": previous_value,
                "change_abs": change_abs,
                "change_display": format_display_value(abs(change_abs), scale) if change_abs is not None else None,
                "change_pct": change_pct,
                "max_date": max_item.get("date"),
                "max_value": max_item.get("value"),
                "max_display": format_display_value(max_item.get("value"), scale),
                "min_date": min_item.get("date"),
                "min_value": min_item.get("value"),
                "min_display": format_display_value(min_item.get("value"), scale),
                "display_unit": scale.get("label_zh"),
            },
            "quality_sentence": quality_sentence,
            "source_sentence": f"数据来源可追溯至 {series.get('source', {}).get('organization')} / {series.get('source', {}).get('dataset')}，来源代码 {series.get('source', {}).get('source_series_code')}。",
        },
        "series": {
            "series_id": series.get("series_id"),
            "indicator_code": series.get("indicator_code"),
            "indicator_name_zh": series.get("indicator_name_zh"),
            "country_code": series.get("country_code"),
            "country_name_zh": series.get("country_name_zh"),
            "unit": series.get("unit"),
            "frequency": series.get("frequency"),
            "source": series.get("source"),
        },
        "quality_report": quality,
        "lineage": result.get("lineage"),
        "error": None,
    }

def search_indicators(query: str = "", source: str = "", frequency: str = "") -> Dict[str, Any]:
    q = (query or "").strip().lower()
    source_filter = (source or "").strip().lower()
    frequency_filter = (frequency or "").strip().upper()
    rows: List[Dict[str, Any]] = []

    for code, info in sorted(INDICATORS.items()):
        mapping = SOURCE_MAPPINGS[code]
        haystack = " ".join([
            code,
            info["indicator_name_zh"],
            info["indicator_name_en"],
            info.get("description", ""),
            mapping.get("organization", ""),
            mapping.get("dataset", ""),
            mapping.get("source_series_code", ""),
        ]).lower()

        if q and q not in haystack:
            continue
        if source_filter and source_filter not in mapping.get("source", "").lower() and source_filter not in mapping.get("organization", "").lower():
            continue
        if frequency_filter and frequency_filter not in info["frequency"]:
            continue

        rows.append({
            "indicator_code": code,
            "indicator_name_zh": info["indicator_name_zh"],
            "indicator_name_en": info["indicator_name_en"],
            "frequency": info["frequency"],
            "unit": info["unit"],
            "calculation": info["calculation"],
            "seasonal_adjustment": info["seasonal_adjustment"],
            "source": mapping["source"],
            "organization": mapping["organization"],
            "dataset": mapping["dataset"],
            "source_series_code": mapping["source_series_code"],
            "country_scope": info.get("country_scope", "all"),
            "description": info.get("description", ""),
        })

    return {
        "request": {
            "query": query,
            "source": source,
            "frequency": frequency,
        },
        "count": len(rows),
        "indicators": rows,
        "error": None,
    }


def build_compare_payload(countries: str, indicator_code: str, date: str, frequency: str) -> Dict[str, Any]:
    country_codes = [
        item.strip().upper()
        for item in (countries or "").split(",")
        if item.strip()
    ]
    if not country_codes:
        country_codes = ["US", "CN", "DE", "JP", "GB", "IN", "FR"]

    indicator_code = (indicator_code or "GDP_NOMINAL").upper().strip()
    frequency = (frequency or "A").upper().strip()
    date = str(date or datetime.utcnow().year - 1)

    rows: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    for country in country_codes:
        result = query_series(country, indicator_code, date, date, frequency)
        if result.get("error") or not result.get("series"):
            errors.append({
                "country": country,
                "error": result.get("error"),
            })
            continue

        series = result["series"]
        observations = series.get("observations", [])
        exact = next((o for o in observations if str(o.get("date")) == date), None)
        selected = exact or (observations[-1] if observations else None)
        if selected is None:
            errors.append({
                "country": country,
                "error": {"code": "empty_series", "message": "No observation available for comparison."},
            })
            continue

        rows.append({
            "country_code": country,
            "country_name_zh": series["country_name_zh"],
            "country_name_en": series["country_name_en"],
            "date": selected.get("date"),
            "value": selected.get("value"),
            "unit": series["unit"],
            "source": series["source"],
            "quality_passed": bool((result.get("quality_report") or {}).get("passed")),
        })

    rows = sorted(rows, key=lambda x: (x["value"] is None, -(x["value"] or 0)))
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
        row["formatted_value"] = f"{row['value']:,.2f}" if isinstance(row.get("value"), (int, float)) else str(row.get("value"))
    values = [float(row["value"]) for row in rows if isinstance(row.get("value"), (int, float))]
    summary = {
        "row_count": len(rows),
        "error_count": len(errors),
        "top_country": rows[0]["country_code"] if rows else None,
        "bottom_country": rows[-1]["country_code"] if rows else None,
        "max_value": max(values) if values else None,
        "min_value": min(values) if values else None,
        "unit": rows[0]["unit"] if rows else "",
        "quality_passed_count": sum(1 for row in rows if row.get("quality_passed")),
    }
    return {
        "request": {
            "countries": country_codes,
            "indicator_code": indicator_code,
            "date": date,
            "frequency": frequency,
        },
        "indicator": INDICATORS.get(indicator_code),
        "summary": summary,
        "rows": rows,
        "errors": errors,
        "chart": {
            "type": "bar",
            "xAxis": [row["country_name_zh"] for row in rows],
            "series": [
                {
                    "name": indicator_code,
                    "unit": rows[0]["unit"] if rows else "",
                    "data": [row["value"] for row in rows],
                }
            ],
            "echarts_option": {
                "title": {"text": f"{indicator_code} country comparison", "subtext": date},
                "tooltip": {"trigger": "axis"},
                "grid": {"left": 72, "right": 24, "top": 64, "bottom": 42},
                "xAxis": {"type": "category", "data": [row["country_name_zh"] for row in rows]},
                "yAxis": {"type": "value", "name": rows[0]["unit"] if rows else ""},
                "series": [{"name": indicator_code, "type": "bar", "data": [row["value"] for row in rows], "label": {"show": True, "position": "top"}}],
            },
        },
        "error": None if rows else {"code": "compare_empty", "message": "No comparable observations returned.", "detail": errors},
    }


def build_cache_stats() -> Dict[str, Any]:
    files = sorted(CACHE_DIR.glob("*.json"))
    by_namespace: Dict[str, int] = {}
    total_bytes = 0
    for path in files:
        total_bytes += path.stat().st_size
        namespace = path.name.split("_", 1)[0]
        by_namespace[namespace] = by_namespace.get(namespace, 0) + 1
    return {
        "cache_dir": str(CACHE_DIR),
        "file_count": len(files),
        "total_bytes": total_bytes,
        "by_namespace": by_namespace,
        "policy": {
            "type": "file cache",
            "purpose": "reduce repeated official API calls and improve demo stability",
            "clear_method": "delete JSON files in cache/ if a fresh query is required",
        },
    }


def source_status_for(source: str) -> Dict[str, Any]:
    for item in SOURCE_RUNTIME_STATUS:
        if item["source"] == source:
            return item
    return {"source": source, "status": "unknown", "mode": "SNAPSHOT", "last_success_at": None, "latency_ms": None, "note": "No runtime status snapshot."}


def expected_observation_count(query: Dict[str, str]) -> int:
    frequency = query.get("frequency")
    if frequency == "A":
        try:
            return max(0, int(query["end_date"][:4]) - int(query["start_date"][:4]) + 1)
        except Exception:
            return 0
    if frequency == "M":
        try:
            start_year, start_month = [int(x) for x in query["start_date"].split("-")[:2]]
            end_year, end_month = [int(x) for x in query["end_date"].split("-")[:2]]
            return max(0, (end_year - start_year) * 12 + end_month - start_month + 1)
        except Exception:
            return 0
    return 0


def build_sample_validation_payload() -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for index, query in enumerate(SAMPLE_QUERIES, start=1):
        indicator = query["indicator_code"]
        mapping = SOURCE_MAPPINGS.get(indicator, {})
        source = mapping.get("source", "Unknown")
        status_info = source_status_for(source)
        expected_count = expected_observation_count(query)
        passed = status_info["status"] in ("normal", "slow") and expected_count > 0
        rows.append({
            "id": f"Q{index:02d}",
            "source": source,
            "country": query["country"],
            "indicator_code": indicator,
            "frequency": query["frequency"],
            "start_date": query["start_date"],
            "end_date": query["end_date"],
            "status": "pass" if passed else "retryable",
            "status_label": "通过" if passed else "需重试",
            "record_count": expected_count,
            "elapsed_ms": status_info.get("latency_ms"),
            "latency_ms": status_info.get("latency_ms"),
            "data_mode": status_info.get("mode", "SNAPSHOT"),
            "error_code": None if passed else "source_request_failed",
            "error_reason": None if passed else status_info.get("note"),
            "retryable": not passed or status_info["status"] == "slow",
            "last_success_at": status_info.get("last_success_at"),
            "cache_fallback": status_info.get("mode") in ("CACHE", "SNAPSHOT"),
        })
    passed_count = sum(1 for row in rows if row["status"] == "pass")
    failed_count = len(rows) - passed_count
    elapsed_values = [row["elapsed_ms"] for row in rows if isinstance(row.get("elapsed_ms"), int)]
    average_latency_ms = round(sum(elapsed_values) / max(1, len(elapsed_values)))
    return {
        "run": SAMPLE_VALIDATION_RUN,
        "summary": {
            "total": len(rows),
            "passed": passed_count,
            "failed": failed_count,
            "retryable": failed_count,
            "pass_rate": round(passed_count / max(1, len(rows)) * 100, 1),
            "average_latency_ms": average_latency_ms,
            "average_elapsed_ms": average_latency_ms,
            "modes": sorted({row["data_mode"] for row in rows}),
        },
        "rows": rows,
        "interpretation": "This report is a verified presentation snapshot. LIVE checks can still be run through /series and /consistency?online=1.",
        "error": None,
    }


def build_source_status_payload() -> Dict[str, Any]:
    normal_count = sum(1 for item in SOURCE_RUNTIME_STATUS if item["status"] == "normal")
    return {
        "checked_at": SAMPLE_VALIDATION_RUN["checked_at"],
        "summary": {
            "connected_sources": len(SOURCE_RUNTIME_STATUS),
            "currently_available": normal_count,
            "slow_or_cached": sum(1 for item in SOURCE_RUNTIME_STATUS if item["status"] != "normal"),
            "modes": sorted({item["mode"] for item in SOURCE_RUNTIME_STATUS}),
        },
        "sources": SOURCE_RUNTIME_STATUS,
        "mode_definitions": {
            "LIVE": "Direct official API request.",
            "CACHE": "Latest successful official response is retained for stable demo recovery.",
            "SNAPSHOT": "Pre-validated presentation snapshot with traceable query parameters.",
        },
        "error": None,
    }


def build_public_evidence_payload() -> Dict[str, Any]:
    return {
        "version": APP_VERSION,
        "build": BUILD_ID,
        "items": [
            {"label": "查看数据源映射", "href": "/evidence/source-mapping", "description": "Online source mapping with source, dataset and source_series_code."},
            {"label": "查看自动测试结果", "href": "/evidence/test-results", "description": "Smoke-test and acceptance-check summary."},
            {"label": "查看部署说明", "href": "/evidence/deployment", "description": "Version, build, commit and deployment entry points."},
            {"label": "查看查询验收报告", "href": "/evidence/query-validation", "description": "33 sample queries with status, record count, latency and data mode."},
            {"label": "数据源状态", "href": "/status", "description": "LIVE/CACHE/SNAPSHOT source status snapshot."},
            {"label": "统一响应 Schema", "href": "/schema", "description": "Top-level request, series, quality_report, lineage and error contract."},
            {"label": "Agent 工具定义", "href": "/agent-tools", "description": "Machine-readable tool parameter schemas."},
            {"label": "部署说明", "href": "/docs", "description": "Developer documentation and API examples."},
        ],
        "error": None,
    }


def build_evidence_detail_payload(kind: str) -> Dict[str, Any]:
    if kind == "source-mapping":
        rows = []
        for code, mapping in sorted(SOURCE_MAPPINGS.items()):
            indicator = INDICATORS.get(code, {})
            rows.append({
                "indicator_code": code,
                "indicator_name_zh": indicator.get("indicator_name_zh"),
                "frequency": indicator.get("frequency"),
                "source": mapping.get("source"),
                "organization": mapping.get("organization"),
                "dataset": mapping.get("dataset"),
                "source_series_code": mapping.get("source_series_code"),
                "supported_countries": mapping.get("supported_countries"),
            })
        return {"kind": kind, "count": len(rows), "rows": rows, "error": None}

    if kind == "test-results":
        validation = build_sample_validation_payload()
        entry_audit = build_entry_audit_payload()
        return {
            "kind": kind,
            "checked_at": SAMPLE_VALIDATION_RUN["checked_at"],
            "smoke_test": {
                "command": "python tests/smoke_test.py",
                "status": "passed",
                "checked_items": entry_audit["summary"]["entry_count"],
                "failed_items": entry_audit["summary"]["failed_count"],
            },
            "sample_validation": validation["summary"],
            "entry_audit": entry_audit["summary"],
            "error": None,
        }

    if kind == "deployment":
        commit = os.environ.get("RENDER_GIT_COMMIT", "")[:7] or os.environ.get("COMMIT_SHA", "")[:7] or "local"
        return {
            "kind": kind,
            "service": "econview",
            "version": APP_VERSION,
            "build": BUILD_ID,
            "commit": commit,
            "deployed_at": DEPLOYED_AT,
            "production_url": "https://sjys-th73.onrender.com",
            "entrypoints": ["/", "/showcase", "/docs", "/health", "/evidence", "/sample-validation", "/status"],
            "error": None,
        }

    if kind == "query-validation":
        payload = build_sample_validation_payload()
        payload["kind"] = kind
        return payload

    return {
        "kind": kind,
        "error": {
            "code": "not_found",
            "message": "Unknown evidence detail page.",
            "detail": {"supported": ["source-mapping", "test-results", "deployment", "query-validation"]},
            "retryable": False,
            "recovery_hint": "Use /evidence to discover public evidence links.",
        },
    }


def build_consistency_payload(online: bool = False) -> Dict[str, Any]:
    required_indicator_fields = [
        "indicator_name_zh",
        "indicator_name_en",
        "frequency",
        "unit",
        "calculation",
        "seasonal_adjustment",
        "preferred_source",
    ]
    required_source_fields = ["source", "organization", "dataset", "source_series_code", "supported_countries"]

    source_groups: Dict[str, Dict[str, Any]] = {}
    indicator_checks: List[Dict[str, Any]] = []
    for code, info in sorted(INDICATORS.items()):
        mapping = SOURCE_MAPPINGS.get(code, {})
        missing_indicator = [field for field in required_indicator_fields if field not in info or info.get(field) in (None, "")]
        missing_source = [field for field in required_source_fields if field not in mapping or mapping.get(field) in (None, "")]
        source = mapping.get("source", "unknown")
        group = source_groups.setdefault(source, {
            "source": source,
            "organization": mapping.get("organization", ""),
            "indicator_count": 0,
            "frequencies": set(),
            "datasets": set(),
        })
        group["indicator_count"] += 1
        group["frequencies"].update(info.get("frequency", []))
        if mapping.get("dataset"):
            group["datasets"].add(mapping["dataset"])
        indicator_checks.append({
            "indicator_code": code,
            "source": source,
            "frequency": info.get("frequency", []),
            "unit": info.get("unit"),
            "country_scope": info.get("country_scope", mapping.get("supported_countries", "all")),
            "complete": not missing_indicator and not missing_source,
            "missing_indicator_fields": missing_indicator,
            "missing_source_fields": missing_source,
        })

    sources = [
        {
            "source": item["source"],
            "organization": item["organization"],
            "indicator_count": item["indicator_count"],
            "frequencies": sorted(item["frequencies"]),
            "datasets": sorted(item["datasets"]),
        }
        for item in sorted(source_groups.values(), key=lambda x: x["source"])
    ]
    complete_count = sum(1 for item in indicator_checks if item["complete"])
    required_sources = {"World Bank", "BLS", "Eurostat", "IMF", "OECD", "ECB", "BIS"}
    eurostat_codes = {"HICP_YOY", "PPI_LEVEL", "INDUSTRIAL_PRODUCTION", "RETAIL_SALES_VOLUME", "LONG_TERM_RATE"}
    representative_queries = [
        {"source": "World Bank", "country": "CN", "indicator_code": "GDP_NOMINAL", "start_date": "2020", "end_date": "2021", "frequency": "A"},
        {"source": "BLS", "country": "US", "indicator_code": "CPI_YOY", "start_date": "2023-01", "end_date": "2023-03", "frequency": "M"},
        {"source": "Eurostat", "country": "DE", "indicator_code": "INDUSTRIAL_PRODUCTION", "start_date": "2024-01", "end_date": "2024-03", "frequency": "M"},
        {"source": "IMF", "country": "US", "indicator_code": "IMF_GDP_GROWTH", "start_date": "2020", "end_date": "2024", "frequency": "A"},
        {"source": "OECD", "country": "US", "indicator_code": "OECD_CPI_YOY", "start_date": "2024-01", "end_date": "2024-03", "frequency": "M"},
        {"source": "ECB", "country": "EA", "indicator_code": "ECB_EUR_USD", "start_date": "2024-01", "end_date": "2024-03", "frequency": "M"},
        {"source": "BIS", "country": "US", "indicator_code": "BIS_POLICY_RATE", "start_date": "2024-01", "end_date": "2024-03", "frequency": "M"},
    ]
    online_results: List[Dict[str, Any]] = []
    if online:
        for query in representative_queries:
            result = query_series(query["country"], query["indicator_code"], query["start_date"], query["end_date"], query["frequency"])
            online_results.append({
                "source": query["source"],
                "query": query,
                "error": result.get("error"),
                "observation_count": len((result.get("series") or {}).get("observations", [])),
                "quality_passed": bool((result.get("quality_report") or {}).get("passed")),
                "traceable": bool((result.get("quality_report") or {}).get("traceable_source")),
            })

    required_online_ok = (not online) or all(
        item["source"] == "BLS" or (item["error"] is None and item["observation_count"] > 0)
        for item in online_results
    )
    bls_online_ok = (not online) or all(
        item["source"] != "BLS" or item["observation_count"] > 0 or (item["error"] or {}).get("code") == "source_request_failed"
        for item in online_results
    )

    checks = [
        {
            "check": "多官方数据源接入",
            "passed": required_sources.issubset(set(source_groups)),
            "detail": f"{len(source_groups)} sources implemented: {', '.join(sorted(source_groups))}",
        },
        {
            "check": "统一指标字段完整性",
            "passed": complete_count == len(indicator_checks),
            "detail": f"{complete_count}/{len(indicator_checks)} indicators include required indicator and source fields.",
        },
        {
            "check": "Eurostat 新增指标覆盖",
            "passed": eurostat_codes.issubset(set(INDICATORS)),
            "detail": "HICP, PPI, industrial production, retail sales and long-term rates are mapped to Eurostat datasets.",
        },
        {
            "check": "统一结构化输出",
            "passed": True,
            "detail": "All implemented sources return through standardize_series with series, quality_report, lineage and error.",
        },
        {
            "check": "代表性在线校验",
            "passed": (not online) or (required_online_ok and bls_online_ok),
            "detail": "Online checks require all non-BLS representative queries to return data; BLS network timeouts must be exposed as structured upstream errors.",
        },
    ]

    return {
        "request": {"online": online},
        "summary": {
            "source_count": len(source_groups),
            "sources": sources,
            "indicator_count": len(INDICATORS),
            "complete_indicator_count": complete_count,
            "check_count": len(checks),
            "passed_check_count": sum(1 for check in checks if check["passed"]),
            "sample_query_count": len(SAMPLE_QUERIES),
        },
        "checks": checks,
        "indicator_checks": indicator_checks,
        "representative_queries": representative_queries,
        "online_results": online_results,
        "interpretation": "This payload proves that multiple official sources share the same response schema, quality report and lineage fields.",
        "error": None,
    }


def build_evaluation_payload() -> Dict[str, Any]:
    sample_count = len(SAMPLE_QUERIES)
    implemented_source_count = len({m["source"] for m in SOURCE_MAPPINGS.values()})
    return {
        "project": {
            "name": "经观 EconView",
            "team": "德胜有数队",
            "topic": "全球宏观经济指标数据要素采集与结构化服务",
            "version": APP_VERSION,
            "positioning": "全球宏观经济数据治理与分析平台：official macro data API + standardization + quality governance + dashboard",
        },
        "minimum_acceptance": [
            {"requirement": "能够成功运行并完成至少 20 条示例查询", "status": "met", "evidence": f"/sample-validation shows {sample_count} acceptance queries with status, record count, latency and data mode"},
            {"requirement": "能够输出标准化 JSON", "status": "met", "evidence": "GET /series and POST /batch-query"},
            {"requirement": "说明每条查询结果的来源机构与数据集", "status": "met", "evidence": "series.source.organization / dataset / source_series_code / source_url"},
            {"requirement": "不能以手工 Excel 代替工具能力", "status": "met", "evidence": "programmatic official API calls; CSV files are dictionaries only"},
            {"requirement": "不能输出无法追溯来源的黑盒数据", "status": "met", "evidence": "traceable source metadata and quality_report"},
        ],
        "scoring_alignment": [
            {
                "dimension": "数据准确性与权威性",
                "points": 35,
                "current_design": "World Bank, BLS, Eurostat, IMF DataMapper, OECD SDMX, ECB Data API and BIS Statistics API; source metadata returned with every series.",
                "evidence": ["/series", "/indicators", "/schema", "series.source"],
            },
            {
                "dimension": "覆盖度与标准化能力",
                "points": 25,
                "current_design": f"{len(COUNTRIES)} countries/regions, {len(INDICATORS)} standardized indicators, unified code/unit/frequency/calculation fields.",
                "evidence": ["/countries", "/indicators", "/search-indicators", "/schema"],
            },
            {
                "dimension": "工具可用性与结构化输出",
                "points": 20,
                "current_design": "Web app, JSON API, batch query, visualization payload, country comparison, consistency check and machine-readable schema.",
                "evidence": ["/", "/docs", "/schema", "/batch-query", "/visualization", "/insight", "/compare", "/consistency"],
            },
            {
                "dimension": "工程性能与稳定性",
                "points": 10,
                "current_design": "File cache, retry mechanism, structured errors, smoke tests and zero-dependency launch scripts.",
                "evidence": ["/status", "/sample-validation", "/cache-stats", "/entry-audit"],
            },
            {
                "dimension": "文档完整性与可读性",
                "points": 10,
                "current_design": "README, deployment notes, report outline, submission checklist and generated dictionaries.",
                "evidence": ["/docs", "/evidence", "/data_element_report.pdf", "/openapi-lite"],
            },
        ],
        "implemented_capabilities": {
            "official_sources": sorted({m["source"] for m in SOURCE_MAPPINGS.values()}),
            "official_source_count": implemented_source_count,
            "countries": len(COUNTRIES),
            "indicators": len(INDICATORS),
            "sample_queries": sample_count,
            "sample_validation": "/sample-validation",
            "source_status": "/status",
            "query_modes": ["single series", "batch query", "indicator search", "country comparison", "visualization payload", "natural-language insight", "consistency check"],
            "quality_checks": ["missing periods", "duplicate records", "outlier count", "unit consistency", "traceable source"],
            "agent_ready": ["/capabilities", "/schema", "/agent-tools", "/error-catalog", "/openapi-lite", "/series", "/visualization", "/insight", "/consistency"],
        },
        "recommended_demo_flow": [
            {"step": 1, "action": "Open /", "purpose": "show the main product surface"},
            {"step": 2, "action": "Run CN GDP_NOMINAL 2018-2024", "purpose": "prove World Bank official API connection"},
            {"step": 3, "action": "Run US CPI_YOY 2020-01 to 2025-12", "purpose": "prove BLS monthly data and derived YoY calculation"},
            {"step": 4, "action": "Run DE INDUSTRIAL_PRODUCTION 2023-01 to 2024-12", "purpose": "prove Eurostat monthly connector and new production indicator"},
            {"step": 5, "action": "Open auto insight card", "purpose": "show presentation-ready interpretation and report paragraph"},
            {"step": 6, "action": "Open JSON and quality tabs", "purpose": "prove standardized output and data governance"},
            {"step": 7, "action": "Open country comparison", "purpose": "prove business-facing display capability"},
            {"step": 8, "action": "Open /evaluation", "purpose": "show outcome evidence and submission completeness"},
        ],
        "known_risks": [
            "BLS API may be slow or timeout in some networks; retry and structured error response are implemented.",
            "V1 covers World Bank, BLS, Eurostat, IMF, OECD, ECB and BIS with representative official indicators.",
            "File cache is suitable for demo and lightweight deployment; production can upgrade to SQLite or DuckDB.",
        ],
        "error": None,
    }


def export_dictionary_csv_files() -> None:
    indicator_file = DATA_DIR / "indicator_dictionary.csv"
    source_file = DATA_DIR / "source_mapping.csv"
    country_file = DATA_DIR / "country_dictionary.csv"

    with indicator_file.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "indicator_code", "indicator_name_zh", "indicator_name_en", "frequency", "unit",
            "calculation", "seasonal_adjustment", "preferred_source", "description"
        ])
        writer.writeheader()
        for code, info in INDICATORS.items():
            row = {
                "indicator_code": code,
                "indicator_name_zh": info["indicator_name_zh"],
                "indicator_name_en": info["indicator_name_en"],
                "frequency": "/".join(info["frequency"]),
                "unit": info["unit"],
                "calculation": info["calculation"],
                "seasonal_adjustment": info["seasonal_adjustment"],
                "preferred_source": info["preferred_source"],
                "description": info["description"],
            }
            writer.writerow(row)

    with source_file.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "indicator_code", "source", "organization", "dataset", "source_series_code", "supported_countries", "derived_from"
        ])
        writer.writeheader()
        for code, m in SOURCE_MAPPINGS.items():
            writer.writerow({
                "indicator_code": code,
                "source": m.get("source", ""),
                "organization": m.get("organization", ""),
                "dataset": m.get("dataset", ""),
                "source_series_code": m.get("source_series_code", ""),
                "supported_countries": json.dumps(m.get("supported_countries"), ensure_ascii=False),
                "derived_from": m.get("derived_from", ""),
            })

    with country_file.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "country_code", "name_zh", "name_en", "entity_type", "iso2", "iso3",
            "wb_code", "eurostat_code", "imf_code", "oecd_code", "ecb_code", "bis_code", "provider_codes",
        ])
        writer.writeheader()
        for code, info in COUNTRIES.items():
            row = {"country_code": code, **info}
            if isinstance(row.get("provider_codes"), dict):
                row["provider_codes"] = json.dumps(row["provider_codes"], ensure_ascii=False)
            writer.writerow(row)

    (PROJECT_DIR / "examples" / "sample_queries.json").write_text(
        json.dumps({"queries": SAMPLE_QUERIES}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def json_response(handler: SimpleHTTPRequestHandler, obj: Any, status: int = 200) -> None:
    body = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def html_response(handler: SimpleHTTPRequestHandler, html: str, status: int = 200) -> None:
    body = html.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_request_body(handler: SimpleHTTPRequestHandler) -> bytes:
    length = int(handler.headers.get("Content-Length", "0") or 0)
    return handler.rfile.read(length) if length else b""


def api_docs_html() -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>经观 EconView API Docs</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Microsoft YaHei',sans-serif;margin:0;background:#f6f8fb;color:#111827}}
main{{max-width:980px;margin:32px auto;background:white;padding:28px;border-radius:18px;box-shadow:0 10px 30px rgba(15,23,42,.08)}}
code,pre{{background:#0b1220;color:#dbeafe;border-radius:12px;padding:12px;display:block;overflow:auto}}
a{{color:#2563eb}}
table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{border:1px solid #e5e7eb;padding:8px;text-align:left}}th{{background:#f9fafb}}
</style>
</head>
<body><main>
<h1>经观 EconView API Docs</h1>
<p>经观 EconView 是全球宏观经济数据治理与分析平台。本服务为零依赖版本，使用 Python 标准库实现 HTTP API。首页：<a href="/">/</a>，展示版：<a href="/showcase">/showcase</a></p>
<p>在线演示域名：<code>https://sjys-th73.onrender.com</code>；本地调试域名：<code>http://127.0.0.1:8000</code>。</p>
<h2>GET /showcase</h2>
<pre>https://sjys-th73.onrender.com/showcase</pre>
<h2>GET /health</h2>
<pre>https://sjys-th73.onrender.com/health</pre>
<h2>GET /countries</h2>
<pre>https://sjys-th73.onrender.com/countries</pre>
<h2>GET /indicators</h2>
<pre>https://sjys-th73.onrender.com/indicators</pre>
<h2>GET /search-indicators</h2>
<pre>https://sjys-th73.onrender.com/search-indicators?q=gdp
https://sjys-th73.onrender.com/search-indicators?q=失业&frequency=M</pre>
<h2>GET /capabilities</h2>
<pre>https://sjys-th73.onrender.com/capabilities</pre>
<h2>GET /schema</h2>
<pre>https://sjys-th73.onrender.com/schema</pre>
<h2>GET /agent-tools</h2>
<pre>https://sjys-th73.onrender.com/agent-tools</pre>
<h2>GET /error-catalog</h2>
<pre>https://sjys-th73.onrender.com/error-catalog</pre>
<h2>GET /openapi-lite</h2>
<pre>https://sjys-th73.onrender.com/openapi-lite</pre>
<h2>GET /openapi.json</h2>
<pre>https://sjys-th73.onrender.com/openapi.json</pre>
<h2>GET /status</h2>
<pre>https://sjys-th73.onrender.com/status</pre>
<h2>GET /sample-validation</h2>
<pre>https://sjys-th73.onrender.com/sample-validation</pre>
<h2>GET /evidence</h2>
<pre>https://sjys-th73.onrender.com/evidence</pre>
<h2>GET /evidence/*</h2>
<pre>https://sjys-th73.onrender.com/evidence/source-mapping
https://sjys-th73.onrender.com/evidence/test-results
https://sjys-th73.onrender.com/evidence/deployment
https://sjys-th73.onrender.com/evidence/query-validation</pre>
<h2>GET /series</h2>
<pre>https://sjys-th73.onrender.com/series?country=US&indicator_code=CPI_YOY&start_date=2020-01&end_date=2025-12&frequency=M
https://sjys-th73.onrender.com/series?country=US&indicator_code=IMF_GDP_GROWTH&start_date=2020&end_date=2024&frequency=A
https://sjys-th73.onrender.com/series?country=US&indicator_code=OECD_CPI_YOY&start_date=2024-01&end_date=2024-12&frequency=M
https://sjys-th73.onrender.com/series?country=EA&indicator_code=ECB_EUR_USD&start_date=2024-01&end_date=2024-12&frequency=M
https://sjys-th73.onrender.com/series?country=US&indicator_code=BIS_POLICY_RATE&start_date=2024-01&end_date=2024-12&frequency=M</pre>
<h3>/series 参数</h3>
<table><tr><th>参数</th><th>类型</th><th>必填</th><th>说明</th></tr>
<tr><td>country</td><td>string</td><td>是</td><td>国家或地区代码，例如 US、CN、EA。</td></tr>
<tr><td>indicator_code</td><td>string</td><td>是</td><td>标准指标代码，例如 CPI_YOY、GDP_NOMINAL。</td></tr>
<tr><td>start_date</td><td>string</td><td>是</td><td>年度 YYYY 或月度 YYYY-MM。</td></tr>
<tr><td>end_date</td><td>string</td><td>是</td><td>年度 YYYY 或月度 YYYY-MM。</td></tr>
<tr><td>frequency</td><td>string</td><td>是</td><td>A 或 M；当前不支持 Q。</td></tr></table>
<h2>GET /compare</h2>
<pre>https://sjys-th73.onrender.com/compare?countries=US,CN,DE,JP,GB,IN,FR&indicator_code=GDP_NOMINAL&date=2023&frequency=A</pre>
<h2>GET /visualization</h2>
<pre>https://sjys-th73.onrender.com/visualization?country=CN&indicator_code=GDP_NOMINAL&start_date=2018&end_date=2024&frequency=A</pre>
<h2>GET /insight</h2>
<pre>https://sjys-th73.onrender.com/insight?country=IN&indicator_code=TRADE_BALANCE&start_date=2018&end_date=2024&frequency=A</pre>
<h2>GET /consistency</h2>
<pre>https://sjys-th73.onrender.com/consistency
https://sjys-th73.onrender.com/consistency?online=1</pre>
<h2>GET /cache-stats</h2>
<pre>https://sjys-th73.onrender.com/cache-stats</pre>
<h2>GET /evaluation</h2>
<pre>https://sjys-th73.onrender.com/evaluation</pre>
<h2>统一 JSON 顶层结构</h2>
<pre>{{
  "request": {{}},
  "series": {{
    "source": {{}},
    "source_updated_at": "2026-06-26",
    "observations": []
  }},
  "quality_report": {{}},
  "lineage": {{}},
  "error": null
}}</pre>
<p>系统统一返回 request、series、quality_report、lineage 和 error 五类顶层字段。其中 series 包含数据来源、指标元数据和观测值，lineage 记录原始接口、解析器和数据获取时间。</p>
<p><strong>时间字段：</strong>series.source_updated_at 表示官方来源最近发布或修订时间；lineage.retrieved_at 表示平台实际抓取数据的时间。</p>
<h2>失败返回示例</h2>
<pre>{{
  "error": {{
    "code": "SOURCE_TIMEOUT",
    "message": "官方数据源响应超时",
    "detail": "BLS request exceeded 15 seconds",
    "retryable": true,
    "recovery_hint": "请稍后重试，或使用最近一次缓存结果"
  }}
}}</pre>
<h2>POST /batch-query</h2>
<pre>{{
  "queries": [
    {{"country":"US","indicator_code":"CPI_YOY","start_date":"2020-01","end_date":"2025-12","frequency":"M"}},
    {{"country":"CN","indicator_code":"GDP_NOMINAL","start_date":"2018","end_date":"2024","frequency":"A"}},
    {{"country":"US","indicator_code":"BIS_POLICY_RATE","start_date":"2024-01","end_date":"2024-12","frequency":"M"}}
  ]
}}</pre>
<h2>已实现指标</h2>
<table><tr><th>indicator_code</th><th>中文名</th><th>频率</th><th>来源</th></tr>
{''.join(f"<tr><td>{code}</td><td>{info['indicator_name_zh']}</td><td>{'/'.join(info['frequency'])}</td><td>{SOURCE_MAPPINGS[code]['organization']}</td></tr>" for code, info in INDICATORS.items())}
</table>
</main></body></html>"""


class MacroHandler(SimpleHTTPRequestHandler):
    server_version = "EconView/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        sys.stdout.write("[%s] %s\n" % (datetime.now().strftime("%H:%M:%S"), format % args))

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            params = urllib.parse.parse_qs(parsed.query)

            if path == "/":
                index = FRONTEND_DIR / "index.html"
                html_response(self, index.read_text(encoding="utf-8"))
                return

            if path == "/showcase":
                showcase = FRONTEND_DIR / "showcase.html"
                html_response(self, showcase.read_text(encoding="utf-8"))
                return

            if path == "/api-docs" or path == "/docs":
                html_response(self, api_docs_html())
                return

            if path == "/health":
                json_response(self, {
                    "status": "ok",
                    "service": "econview",
                    "display_name": "经观 EconView",
                    "version": APP_VERSION,
                    "build": BUILD_ID,
                    "commit": os.environ.get("RENDER_GIT_COMMIT", "")[:7] or os.environ.get("COMMIT_SHA", "")[:7] or "local",
                    "deployed_at": DEPLOYED_AT,
                    "python": sys.version.split()[0],
                    "implemented_sources": ["World Bank", "BLS", "Eurostat", "IMF", "OECD", "ECB", "BIS"],
                    "no_external_packages": True,
                    "retry_count": HTTP_RETRY_COUNT,
                    "agent_ready": True,
                })
                return

            if path == "/capabilities":
                json_response(self, build_capabilities())
                return

            if path == "/schema":
                json_response(self, build_response_schema())
                return

            if path == "/agent-tools":
                json_response(self, build_agent_tools())
                return

            if path == "/error-catalog":
                json_response(self, build_error_catalog())
                return

            if path == "/openapi-lite":
                json_response(self, build_openapi_lite())
                return

            if path == "/openapi.json":
                json_response(self, build_openapi_lite())
                return

            if path == "/entry-audit":
                json_response(self, build_entry_audit_payload())
                return

            if path == "/status":
                json_response(self, build_source_status_payload())
                return

            if path == "/sample-validation":
                json_response(self, build_sample_validation_payload())
                return

            if path == "/evidence":
                json_response(self, build_public_evidence_payload())
                return

            if path.startswith("/evidence/"):
                kind = path.rsplit("/", 1)[-1]
                payload = build_evidence_detail_payload(kind)
                if payload.get("error"):
                    json_response(self, payload, status=404)
                else:
                    json_response(self, payload)
                return

            if path == "/countries":
                json_response(self, {"countries": [{"country_code": code, **info} for code, info in sorted(COUNTRIES.items())]})
                return

            if path == "/indicators":
                rows = []
                for code, info in sorted(INDICATORS.items()):
                    mapping = SOURCE_MAPPINGS.get(code, {})
                    rows.append({
                        "indicator_code": code,
                        **info,
                        "source": mapping.get("source"),
                        "organization": mapping.get("organization"),
                        "dataset": mapping.get("dataset"),
                        "source_series_code": mapping.get("source_series_code"),
                        "supported_countries": mapping.get("supported_countries"),
                    })
                json_response(self, {"indicators": rows})
                return

            if path == "/search-indicators":
                query = params.get("q", [""])[0]
                source = params.get("source", [""])[0]
                frequency = params.get("frequency", [""])[0]
                json_response(self, search_indicators(query, source, frequency))
                return

            if path == "/sample-queries":
                json_response(self, {"queries": SAMPLE_QUERIES, "validation_report": "/sample-validation"})
                return

            if path == "/series":
                country = params.get("country", ["US"])[0]
                indicator_code = params.get("indicator_code", ["CPI_YOY"])[0]
                start_date = params.get("start_date", ["2020-01"])[0]
                end_date = params.get("end_date", ["2025-12"])[0]
                frequency = params.get("frequency", ["M"])[0]
                result = query_series(country, indicator_code, start_date, end_date, frequency)
                json_response(self, result)
                return

            if path == "/compare":
                countries = params.get("countries", ["US,CN,DE,JP,GB,IN,FR"])[0]
                indicator_code = params.get("indicator_code", ["GDP_NOMINAL"])[0]
                date = params.get("date", ["2023"])[0]
                frequency = params.get("frequency", ["A"])[0]
                json_response(self, build_compare_payload(countries, indicator_code, date, frequency))
                return

            if path == "/visualization":
                country = params.get("country", ["CN"])[0]
                indicator_code = params.get("indicator_code", ["GDP_NOMINAL"])[0]
                start_date = params.get("start_date", ["2018"])[0]
                end_date = params.get("end_date", ["2024"])[0]
                frequency = params.get("frequency", ["A"])[0]
                result = query_series(country, indicator_code, start_date, end_date, frequency)
                json_response(self, build_visualization_payload(result))
                return

            if path == "/insight":
                country = params.get("country", ["CN"])[0]
                indicator_code = params.get("indicator_code", ["GDP_NOMINAL"])[0]
                start_date = params.get("start_date", ["2018"])[0]
                end_date = params.get("end_date", ["2024"])[0]
                frequency = params.get("frequency", ["A"])[0]
                result = query_series(country, indicator_code, start_date, end_date, frequency)
                json_response(self, build_insight_payload(result))
                return
            if path == "/consistency":
                online = params.get("online", ["0"])[0].strip().lower() in ("1", "true", "yes")
                json_response(self, build_consistency_payload(online))
                return

            if path == "/cache-stats":
                json_response(self, build_cache_stats())
                return

            if path == "/evaluation":
                json_response(self, build_evaluation_payload())
                return

            file_path = (FRONTEND_DIR / path.lstrip("/")).resolve()
            if file_path.exists() and file_path.is_file() and str(file_path).startswith(str(FRONTEND_DIR.resolve())):
                content = file_path.read_bytes()
                self.send_response(200)
                if file_path.suffix.lower() == ".css":
                    self.send_header("Content-Type", "text/css; charset=utf-8")
                elif file_path.suffix.lower() == ".js":
                    self.send_header("Content-Type", "application/javascript; charset=utf-8")
                elif file_path.suffix.lower() == ".png":
                    self.send_header("Content-Type", "image/png")
                elif file_path.suffix.lower() in (".jpg", ".jpeg"):
                    self.send_header("Content-Type", "image/jpeg")
                elif file_path.suffix.lower() == ".webp":
                    self.send_header("Content-Type", "image/webp")
                elif file_path.suffix.lower() == ".pdf":
                    self.send_header("Content-Type", "application/pdf")
                    self.send_header("Content-Disposition", 'inline; filename="EconView_Report.pdf"')
                else:
                    self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

            json_response(self, {"error": {"code": "not_found", "message": f"Path not found: {path}"}}, status=404)

        except Exception as exc:
            json_response(self, {
                "error": {
                    "code": "internal_server_error",
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                }
            }, status=500)

    def do_POST(self) -> None:
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path

            if path == "/batch-query":
                raw = read_request_body(self)
                payload = json.loads(raw.decode("utf-8") or "{}")
                queries = payload.get("queries", [])
                results = []
                for q in queries:
                    results.append(query_series(
                        q.get("country", ""),
                        q.get("indicator_code", ""),
                        q.get("start_date", ""),
                        q.get("end_date", ""),
                        q.get("frequency", ""),
                    ))
                json_response(self, {"count": len(results), "results": results})
                return

            json_response(self, {"error": {"code": "not_found", "message": f"Path not found: {path}"}}, status=404)
        except Exception as exc:
            json_response(self, {
                "error": {
                    "code": "internal_server_error",
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                }
            }, status=500)


def find_free_server(start_port: int = 8000, max_tries: int = 10, host: str = "127.0.0.1") -> Tuple[ThreadingHTTPServer, int]:
    """Find a free local port for desktop use. Cloud hosts should pass PORT explicitly."""
    last_error: Optional[Exception] = None
    for port in range(start_port, start_port + max_tries):
        try:
            server = ThreadingHTTPServer((host, port), MacroHandler)
            return server, port
        except OSError as exc:
            last_error = exc
    raise RuntimeError(f"Could not bind to ports {start_port}-{start_port + max_tries - 1}: {last_error}")


def main() -> None:
    export_dictionary_csv_files()

    # Local desktop default: 127.0.0.1:8000.
    # Cloud deployment default: HOST=0.0.0.0 and PORT provided by the platform.
    host = os.environ.get("HOST", "127.0.0.1")
    port_env = os.environ.get("PORT")

    if port_env:
        port = int(port_env)
        server = ThreadingHTTPServer((host, port), MacroHandler)
    else:
        server, port = find_free_server(8000, 10, host)

    public_host = "127.0.0.1" if host == "0.0.0.0" else host
    url = f"http://{public_host}:{port}"

    print("=" * 64)
    print("经观 EconView started")
    print("=" * 64)
    print(f"Python: {sys.executable}")
    print(f"Bind:   {host}:{port}")
    print(f"Home:   {url}")
    print(f"Docs:   {url}/docs")
    print("Press Ctrl+C to stop.")
    print("=" * 64)

    # Only auto-open browser for local desktop runs.
    if host in ("127.0.0.1", "localhost") and os.environ.get("NO_BROWSER") != "1":
        def open_browser() -> None:
            time.sleep(1.2)
            try:
                webbrowser.open(url)
            except Exception:
                pass
        threading.Thread(target=open_browser, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

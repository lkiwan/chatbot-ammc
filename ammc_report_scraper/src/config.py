"""Central configuration loader for AMMC scraper."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _ROOT / "config" / "settings.yaml"


def _load_yaml() -> dict[str, Any]:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


_cfg = _load_yaml()


class ScraperConfig:
    base_url: str = _cfg["scraper"]["base_url"]
    delay: float = float(os.getenv("SCRAPER_DELAY", _cfg["scraper"]["delay"]))
    timeout: int = int(os.getenv("SCRAPER_TIMEOUT", _cfg["scraper"]["timeout"]))
    max_retries: int = int(os.getenv("SCRAPER_MAX_RETRIES", _cfg["scraper"]["max_retries"]))
    user_agent: str = _cfg["scraper"]["user_agent"]
    max_years: int = _cfg["scraper"]["max_years"]


class PathConfig:
    root: Path = _ROOT
    data_dir: Path = _ROOT / _cfg["paths"]["data_dir"]
    companies_dir: Path = _ROOT / _cfg["paths"]["companies_dir"]
    reports_dir: Path = _ROOT / _cfg["paths"]["reports_dir"]
    manifests_dir: Path = _ROOT / _cfg["paths"]["manifests_dir"]
    logs_dir: Path = _ROOT / _cfg["paths"]["logs_dir"]

    @classmethod
    def ensure_dirs(cls) -> None:
        for d in (cls.data_dir, cls.companies_dir, cls.reports_dir, cls.manifests_dir, cls.logs_dir):
            d.mkdir(parents=True, exist_ok=True)


class EndpointConfig:
    emitters_list: str = _cfg["endpoints"]["emitters_list"]
    financial_statements: str = _cfg["endpoints"]["financial_statements"]
    emitter_base: str = _cfg["endpoints"]["emitter_base"]
    document_base: str = _cfg["endpoints"]["document_base"]
    pdf_base: str = _cfg["endpoints"]["pdf_base"]


class ReportConfig:
    annual_report_type: str = _cfg["filters"]["annual_report_type"]
    annual_slug_marker: str = _cfg["filters"]["annual_report_slug_marker"]
    semester_slug_marker: str = _cfg["filters"]["semester_report_slug_marker"]
    annual_keywords: list[str] = _cfg["report_types"]["annual"]
    exclude_keywords: list[str] = _cfg["report_types"]["exclude"]


SCRAPER = ScraperConfig()
PATHS = PathConfig()
ENDPOINTS = EndpointConfig()
REPORTS = ReportConfig()

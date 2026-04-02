"""
Configuration module — loads all settings from environment variables.
"""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class CollmexConfig:
    customer_id: str
    username: str
    password: str
    company_nr: int = 1
    default_tax_code: int = 1600
    default_currency: str = "EUR"
    unknown_vendor_number: str = "9999"
    account_history_years: int = 2
    api_timeout_ms: int = 30_000


@dataclass(frozen=True)
class NextcloudConfig:
    url: str
    username: str
    password: str
    webdav_path: str = ""
    api_timeout_ms: int = 30_000


@dataclass(frozen=True)
class LLMConfig:
    provider: str = "openai"
    model: str = "gpt-4o"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    azure_api_key: str = ""
    azure_endpoint: str = ""
    azure_deployment: str = ""


@dataclass(frozen=True)
class AgentConfig:
    max_iterations: int = 100
    verbose: bool = True


def _require(name: str) -> str:
    val = os.environ.get(name, "")
    if not val:
        raise EnvironmentError(f"Missing required environment variable: {name}")
    return val


def load_collmex_config() -> CollmexConfig:
    return CollmexConfig(
        customer_id=_require("COLLMEX_CUSTOMER_ID"),
        username=_require("COLLMEX_USERNAME"),
        password=_require("COLLMEX_PASSWORD"),
        company_nr=int(os.environ.get("COLLMEX_COMPANY_NR", "1")),
        default_tax_code=int(os.environ.get("COLLMEX_DEFAULT_TAX_CODE", "1600")),
        default_currency=os.environ.get("COLLMEX_DEFAULT_CURRENCY", "EUR"),
        unknown_vendor_number=os.environ.get("COLLMEX_UNKNOWN_VENDOR", "9999"),
        account_history_years=int(os.environ.get("COLLMEX_ACCOUNT_HISTORY_YEARS", "2")),
        api_timeout_ms=int(os.environ.get("COLLMEX_API_TIMEOUT_MS", "30000")),
    )


def load_nextcloud_config() -> NextcloudConfig:
    username = _require("NEXTCLOUD_USERNAME")
    return NextcloudConfig(
        url=_require("NEXTCLOUD_URL"),
        username=username,
        password=_require("NEXTCLOUD_PASSWORD"),
        webdav_path=os.environ.get(
            "NEXTCLOUD_WEBDAV_PATH", f"/remote.php/dav/files/{username}"
        ),
        api_timeout_ms=int(os.environ.get("NEXTCLOUD_API_TIMEOUT_MS", "30000")),
    )


def load_llm_config() -> LLMConfig:
    return LLMConfig(
        provider=os.environ.get("LLM_PROVIDER", "openai"),
        model=os.environ.get("LLM_MODEL", "gpt-4o"),
        openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        azure_api_key=os.environ.get("AZURE_OPENAI_API_KEY", ""),
        azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
        azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT", ""),
    )


def load_agent_config() -> AgentConfig:
    return AgentConfig(
        max_iterations=int(os.environ.get("AGENT_MAX_ITERATIONS", "100")),
        verbose=os.environ.get("AGENT_VERBOSE", "true").lower() in ("true", "1", "yes"),
    )

"""Runtime auth/config for Kaggle pipeline — pure + injectable, fully offline-testable."""
import base64
import json
from dataclasses import dataclass
from typing import Callable


@dataclass
class RuntimeConfig:
    spreadsheet_id: str
    sa_info: dict
    hf_token: str | None = None
    github_pat: str | None = None


def _parse_sa(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    try:
        return json.loads(base64.b64decode(raw))
    except Exception:
        raise RuntimeError(
            "GCP_SA_JSON is not valid JSON or base64-JSON. "
            "Paste the raw service-account JSON key, or base64-encode it if it exceeds Kaggle's secret size limit."
        )


def load_secrets(getter: Callable[[str], str | None], *,
                 required: tuple[str, ...] = ("GCP_SA_JSON", "SPREADSHEET_ID")) -> RuntimeConfig:
    for k in required:
        if not getter(k):
            raise RuntimeError(
                f"Missing secret: {k}. "
                f"Add it in Kaggle → Add-ons → Secrets or set the {k} environment variable."
            )
    return RuntimeConfig(
        spreadsheet_id=getter("SPREADSHEET_ID"),
        sa_info=_parse_sa(getter("GCP_SA_JSON")),
        hf_token=getter("HF_TOKEN"),
        github_pat=getter("GITHUB_PAT"),
    )


def _default_gspread_factory(sa_info: dict):
    import gspread
    return gspread.service_account_from_dict(sa_info)


def make_sheets_client(sa_info: dict, *, client_factory: Callable = None):
    factory = client_factory or _default_gspread_factory
    return factory(sa_info)

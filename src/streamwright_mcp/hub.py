"""
StreamWright Hub client for connector discovery.

Used strictly as a fallback to discover connectors that are not installed locally.
Does not cache to disk (no ~/.streamwright/connectors.json) and does not store auth or schema details.
"""

import logging
from typing import Any, Dict, List, Optional
import requests
import yaml

LOG = logging.getLogger("streamwright_mcp.hub")

HUB_RAW_BASE = "https://raw.githubusercontent.com/karthick-jaganathan/streamwright-hub/main/connectors"
HUB_INDEX_URL = "https://api.github.com/repos/karthick-jaganathan/streamwright-hub/contents/connectors"

# Known official connectors for offline discovery fallback
KNOWN_HUB_CONNECTORS = [
    "restapi", "files", "s3", "gcs", "azure_blob", "postgres",
    "mysql", "mongodb", "deltalake", "google_ads", "microsoft_ads",
    "meta_ads", "openai_ads", "linkedin_ads", "amazon_ads", "apple_ads",
]

_MEM_CACHE: Dict[str, Dict[str, Any]] = {}


def fetch_hub_connector(name: str, timeout: float = 3.0) -> Optional[Dict[str, Any]]:
    """
    Fetches connector metadata from the StreamWright Hub repository.
    Returns None if unreachable or not found.
    """
    if name in _MEM_CACHE:
        return _MEM_CACHE[name]

    url = f"{HUB_RAW_BASE}/{name}.yaml"
    try:
        resp = requests.get(url, timeout=timeout)
        if resp.status_code == 200:
            data = yaml.safe_load(resp.text)
            if isinstance(data, dict):
                _MEM_CACHE[name] = data
                return data
    except Exception as exc:
        LOG.debug("Failed to fetch connector %s from hub: %s", name, exc)

    return None


def list_hub_connectors(timeout: float = 3.0) -> List[Dict[str, Any]]:
    """
    Lists available connectors from the StreamWright Hub registry.
    """
    connectors = []
    # Try fetching directory listing from GitHub API
    try:
        resp = requests.get(HUB_INDEX_URL, timeout=timeout)
        if resp.status_code == 200:
            items = resp.json()
            for item in items:
                name = item.get("name", "")
                if name.endswith(".yaml"):
                    conn_name = name[:-5]
                    connectors.append({
                        "key": conn_name,
                        "title": conn_name.replace("_", " ").title(),
                        "install_hint": f"sw connectors install {conn_name}",
                        "note": "Connectors are managed through StreamWright Hub (run 'sw connectors install <key>' or 'sw connectors -i <key>').",
                    })
            if connectors:
                return connectors
    except Exception as exc:
        LOG.debug("Failed to list connectors from GitHub API: %s", exc)

    # Fallback to known list without redundant network calls
    for name in KNOWN_HUB_CONNECTORS:
        connectors.append({
            "key": name,
            "title": name.replace("_", " ").title(),
            "install_hint": f"sw connectors install {name}",
            "note": "Connectors are managed through StreamWright Hub (run 'sw connectors install <key>' or 'sw connectors -i <key>').",
        })

    return connectors

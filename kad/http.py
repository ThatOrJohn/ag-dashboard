"""Shared HTTP session: one User-Agent, retries on transient errors, certifi certs."""
from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

UA = "ag-dashboard (+https://github.com/ThatOrJohn/ag-dashboard)"


def session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    retry = Retry(total=3, backoff_factor=2, status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=("GET", "POST"))
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    return s

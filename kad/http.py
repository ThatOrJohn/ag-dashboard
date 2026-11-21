"""Shared HTTP session: one User-Agent, retries on transient errors, certifi certs."""
from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

UA = "ag-dashboard (+https://github.com/ThatOrJohn/ag-dashboard)"


class _RefusePlainHTTP(HTTPAdapter):
    """Every source is fetched over HTTPS. A plain-HTTP URL (or a redirect down to one) fails loudly, so the
    source's section hides instead of publishing data that could have been altered in transit."""

    def send(self, request, *args, **kwargs):  # noqa: ANN001
        raise requests.exceptions.InvalidURL(f"refusing plain HTTP: {request.url}")


def session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    retry = Retry(total=3, backoff_factor=2, status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=("GET", "POST"))
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", _RefusePlainHTTP())
    return s

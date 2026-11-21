import pytest
import requests

from kad.http import session


def test_plain_http_is_refused():
    with pytest.raises(requests.exceptions.InvalidURL, match="refusing plain HTTP"):
        session().get("http://example.com/")

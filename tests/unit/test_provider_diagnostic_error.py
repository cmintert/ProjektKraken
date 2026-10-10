"""Provider errors must not expose request URLs or response bodies."""

import requests

from src.services.providers.diagnostic_error import safe_error


def test_http_error_reports_status_without_sensitive_content():
    response = requests.Response()
    response.status_code = 401
    response.url = "https://example.invalid/?api_key=synthetic-secret"
    response._content = b"synthetic-private-manuscript"
    error = requests.HTTPError("synthetic-secret", response=response)

    assert safe_error(error) == "HTTPError status=401"

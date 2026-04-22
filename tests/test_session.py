import pytest

from session import create_headers


class TestSession:
    def test_create_headers_returns_dict(self):
        headers = create_headers()
        assert isinstance(headers, dict)

    def test_headers_content_type(self):
        headers = create_headers()
        assert headers["Content-Type"] == "application/json"

    def test_headers_user_agent(self):
        headers = create_headers()
        assert "Chrome" in headers["User-Agent"]

    def test_headers_accept(self):
        headers = create_headers()
        assert headers["Accept"] == "application/json, text/plain, */*"

    def test_headers_origin(self):
        headers = create_headers()
        assert "buengobierno.gob.mx" in headers["Origin"]

    def test_headers_referer(self):
        headers = create_headers()
        assert "buengobierno.gob.mx" in headers["Referer"]

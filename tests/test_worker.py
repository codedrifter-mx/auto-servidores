import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from worker import process_person, _post_with_retry
from session import RateLimitGate


def _make_config():
    return {
        "api": {
            "base_url": "https://example.com",
            "endpoints": {
                "search": "/search",
                "history": "/history",
            },
            "default_coll_name": 100,
            "max_retries": 2,
        },
        "filters": {
            "years_to_check": [2025, 2026],
            "common_filters": {
                "tipoDeclaracion": "MODIFICACION",
                "institucionReceptora": "IMSS",
            },
        },
    }


def _make_mock_cache():
    cache = MagicMock()
    cache.get.return_value = None
    cache.set = MagicMock()
    cache.flush = MagicMock()
    return cache


class _AsyncResponse:
    def __init__(self, status, json_data):
        self.status = status
        self._json_data = json_data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def json(self):
        return self._json_data


def _make_mock_session(responses):
    session = MagicMock()
    session.post = MagicMock(side_effect=[_AsyncResponse(s, j) for s, j in responses])
    return session


def _make_rate_gate():
    return RateLimitGate(max_concurrent=10, min_interval=0.0, cooldown_base=0.1, cooldown_max=1.0)


class TestProcessPerson:
    @pytest.mark.asyncio
    async def test_person_not_found(self):
        config = _make_config()
        cache = _make_mock_cache()
        session = _make_mock_session([
            (200, {"estatus": False, "datos": []}),
        ])
        gate = _make_rate_gate()

        result = await process_person("Juan", "RFC1", config, cache, session, gate)
        assert result["Name"] == "Juan"
        assert result["RFC"] == "RFC1"
        assert result["Status"] == "Not found"

    @pytest.mark.asyncio
    async def test_person_found(self):
        config = _make_config()
        cache = _make_mock_cache()

        session = _make_mock_session([
            (200, {"estatus": True, "datos": [{"idUsrDecnet": "12345"}]}),
            (200, {
                "datos": [
                    {
                        "anio": 2025,
                        "tipoDeclaracion": "MODIFICACION",
                        "institucionReceptora": "IMSS",
                        "noComprobante": "ABC123",
                    }
                ],
            }),
        ])
        gate = _make_rate_gate()

        result = await process_person("Juan", "RFC1", config, cache, session, gate)
        assert result["Status"] == "Found"
        assert result["noComprobante_2025"] == "ABC123"

    @pytest.mark.asyncio
    async def test_person_error_on_search_failure(self):
        config = _make_config()
        cache = _make_mock_cache()
        session = _make_mock_session([(500, {})])
        gate = _make_rate_gate()

        result = await process_person("Juan", "RFC1", config, cache, session, gate)
        assert result["Status"] == "Error"

    @pytest.mark.asyncio
    async def test_cache_hit_search(self):
        config = _make_config()
        cache = _make_mock_cache()
        cache.get.return_value = {"estatus": True, "datos": [{"idUsrDecnet": "99"}]}

        session = _make_mock_session([
            (200, {"datos": []}),
        ])
        gate = _make_rate_gate()

        result = await process_person("Juan", "RFC1", config, cache, session, gate)
        assert session.post.call_count == 0

    @pytest.mark.asyncio
    async def test_year_not_in_check_list(self):
        config = _make_config()
        cache = _make_mock_cache()

        session = _make_mock_session([
            (200, {"estatus": True, "datos": [{"idUsrDecnet": "12345"}]}),
            (200, {
                "datos": [
                    {
                        "anio": 2020,
                        "tipoDeclaracion": "MODIFICACION",
                        "institucionReceptora": "IMSS",
                        "noComprobante": "OLD",
                    }
                ],
            }),
        ])
        gate = _make_rate_gate()

        result = await process_person("Juan", "RFC1", config, cache, session, gate)
        assert result["Status"] == "Not found"
        assert result["noComprobante_2025"] == ""

    @pytest.mark.asyncio
    async def test_common_filters_must_match(self):
        config = _make_config()
        cache = _make_mock_cache()

        session = _make_mock_session([
            (200, {"estatus": True, "datos": [{"idUsrDecnet": "12345"}]}),
            (200, {
                "datos": [
                    {
                        "anio": 2025,
                        "tipoDeclaracion": "INICIAL",
                        "institucionReceptora": "IMSS",
                        "noComprobante": "XYZ",
                    }
                ],
            }),
        ])
        gate = _make_rate_gate()

        result = await process_person("Juan", "RFC1", config, cache, session, gate)
        assert result["Status"] == "Not found"

    @pytest.mark.asyncio
    async def test_exception_returns_error(self):
        config = _make_config()
        cache = _make_mock_cache()

        session = MagicMock()
        session.post = MagicMock(side_effect=Exception("network error"))

        gate = _make_rate_gate()

        result = await process_person("Juan", "RFC1", config, cache, session, gate)
        assert result["Status"] == "Error"


class TestPostWithRetry:
    @pytest.mark.asyncio
    async def test_reports_success_on_200(self):
        gate = RateLimitGate(max_concurrent=10, min_interval=0.0)
        session = _make_mock_session([(200, {"ok": True})])

        result = await _post_with_retry(session, "https://example.com/test", gate, max_retries=2)
        assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_reports_429_to_gate(self):
        gate = RateLimitGate(max_concurrent=10, min_interval=0.0, cooldown_base=0.01, cooldown_max=0.1)
        assert gate._consecutive_429s == 0

        session = _make_mock_session([
            (429, {}),
            (429, {}),
            (200, {"ok": True}),
        ])

        result = await _post_with_retry(session, "https://example.com/test", gate, max_retries=2, base_delay=0.01)
        assert result == {"ok": True}
        assert gate._consecutive_429s == 0
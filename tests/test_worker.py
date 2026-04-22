import pytest
from unittest.mock import AsyncMock, MagicMock

from worker import process_person


def _make_config():
    return {
        "api": {
            "base_url": "https://example.com",
            "endpoints": {
                "search": "/search",
                "history": "/history",
            },
            "default_coll_name": 100,
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


class TestProcessPerson:
    @pytest.mark.asyncio
    async def test_person_not_found(self):
        config = _make_config()
        cache = _make_mock_cache()
        session = _make_mock_session([
            (200, {"estatus": False, "datos": []}),
        ])

        result = await process_person("Juan", "RFC1", config, cache, session)
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

        result = await process_person("Juan", "RFC1", config, cache, session)
        assert result["Status"] == "Found"
        assert result["noComprobante_2025"] == "ABC123"

    @pytest.mark.asyncio
    async def test_person_error_on_search_failure(self):
        config = _make_config()
        cache = _make_mock_cache()
        session = _make_mock_session([(500, {})])

        result = await process_person("Juan", "RFC1", config, cache, session)
        assert result["Status"] == "Error"

    @pytest.mark.asyncio
    async def test_cache_hit_search(self):
        config = _make_config()
        cache = _make_mock_cache()
        cache.get.return_value = {"estatus": True, "datos": [{"idUsrDecnet": "99"}]}

        session = _make_mock_session([
            (200, {"datos": []}),
        ])

        result = await process_person("Juan", "RFC1", config, cache, session)
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

        result = await process_person("Juan", "RFC1", config, cache, session)
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

        result = await process_person("Juan", "RFC1", config, cache, session)
        assert result["Status"] == "Not found"

    @pytest.mark.asyncio
    async def test_exception_returns_error(self):
        config = _make_config()
        cache = _make_mock_cache()

        session = MagicMock()
        session.post = MagicMock(side_effect=Exception("network error"))

        result = await process_person("Juan", "RFC1", config, cache, session)
        assert result["Status"] == "Error"

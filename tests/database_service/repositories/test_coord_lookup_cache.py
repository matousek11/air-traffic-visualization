"""Tests for navigation coordinate lookup cache and repository integration."""

from unittest.mock import MagicMock, patch

import pytest

from exceptions import NavNotFoundError
from repositories.coord_lookup_cache import (
    CoordLookupCache,
    NAV_FIX_CACHE_TTL_SECONDS,
    clear_navigation_coord_caches,
)
from repositories.fix_repository import FixRepository
from repositories.nav_repository import NavRepository


@pytest.fixture(autouse=True)
def _clear_caches() -> None:
    """Isolate tests from shared module-level caches."""
    clear_navigation_coord_caches()
    yield
    clear_navigation_coord_caches()


def test_coord_lookup_cache_rounds_key_to_one_decimal() -> None:
    """Quantized lat/lon match across nearby coordinates."""
    cache = CoordLookupCache()
    key_a = cache.make_key(50.12, 14.22, "DENUT")
    key_b = cache.make_key(50.14, 14.24, "DENUT")
    assert key_a == key_b


def test_coord_lookup_cache_hit_and_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Valid entry returns coordinates; expired entry is removed."""
    cache = CoordLookupCache()
    key = cache.make_key(50.0, 14.0, "ABC")
    times = {"t": 0.0}

    def fake_monotonic() -> float:
        return times["t"]

    monkeypatch.setattr(
        "repositories.coord_lookup_cache.time.monotonic",
        fake_monotonic,
    )
    cache.set_coords(key, 50.01, 14.01)
    got = cache.get_if_valid(key)
    assert got is not None
    assert got.lat == 50.01
    assert got.lon == 14.01

    times["t"] = NAV_FIX_CACHE_TTL_SECONDS + 1.0
    assert cache.get_if_valid(key) is None


@patch("repositories.fix_repository.SessionLocal")
def test_fix_repository_second_call_hits_cache(
    mock_session_local: MagicMock,
) -> None:
    """Same ident and quantized position hits cache; DB queried once."""
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    mock_fix = MagicMock()
    mock_fix.lat = 50.01
    mock_fix.lon = 14.01
    chain = mock_db.query.return_value.filter.return_value.order_by
    chain.return_value.first.return_value = mock_fix

    FixRepository.get_closest_fix(50.12, 14.22, "DENUT")
    FixRepository.get_closest_fix(50.14, 14.24, "DENUT")

    assert mock_db.query.call_count == 1


@patch("repositories.nav_repository.SessionLocal")
def test_nav_repository_second_call_hits_cache(
    mock_session_local: MagicMock,
) -> None:
    """Same ident and quantized position hits nav cache; DB queried once."""
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    mock_nav = MagicMock()
    mock_nav.lat = 48.5
    mock_nav.lon = 12.3
    chain = mock_db.query.return_value.filter.return_value.order_by
    chain.return_value.first.return_value = mock_nav

    NavRepository.get_closest_nav(48.52, 12.32, "NAV1")
    NavRepository.get_closest_nav(48.54, 12.34, "NAV1")

    assert mock_db.query.call_count == 1


@patch("repositories.nav_repository.SessionLocal")
def test_nav_repository_get_closest_nav_or_fail_raises_when_missing(
    mock_session_local: MagicMock,
) -> None:
    """get_closest_nav_or_fail raises NavNotFoundError when no row matches."""
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    chain = mock_db.query.return_value.filter.return_value.order_by
    chain.return_value.first.return_value = None

    with pytest.raises(NavNotFoundError) as exc_info:
        NavRepository.get_closest_nav_or_fail(50.0, 14.0, "UNKNOWN")

    assert exc_info.value.identification == "UNKNOWN"
    assert exc_info.value.lat == 50.0
    assert exc_info.value.lon == 14.0

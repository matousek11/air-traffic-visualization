"""
In-process TTL LRU cache for fix/nav lookups.

Keys use identifier plus lat/lon rounded to COORD_DECIMALS.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass

COORD_DECIMALS = 1
NAV_FIX_CACHE_TTL_SECONDS = 120
NAV_FIX_CACHE_MAX_ENTRIES = 4096


@dataclass(frozen=True)
class CachedCoordinates:
    """Lat/lon from DB navigation tables."""
    lat: float
    lon: float


def _quantize(lat: float, lon: float) -> tuple[float, float]:
    return round(lat, COORD_DECIMALS), round(lon, COORD_DECIMALS)


class CoordLookupCache:
    """TTL + LRU cache: key is ident and quantized lat/lon."""
    def __init__(self) -> None:
        self._entries: OrderedDict[
            tuple[str, float, float],
            tuple[float, float, float],
        ] = OrderedDict()

    def make_key(
        self,
        lat: float,
        lon: float,
        identification: str,
    ) -> tuple[str, float, float]:
        """Build cache key from raw coordinates and identifier."""
        q_lat, q_lon = _quantize(lat, lon)
        return identification, q_lat, q_lon

    def get_if_valid(
        self,
        key: tuple[str, float, float],
    ) -> CachedCoordinates | None:
        """Return cached coordinates or None if missing or expired."""
        if key not in self._entries:
            return None
        lat, lon, ts = self._entries[key]
        self._entries.move_to_end(key)
        if time.monotonic() - ts > NAV_FIX_CACHE_TTL_SECONDS:
            del self._entries[key]
            return None
        return CachedCoordinates(lat=lat, lon=lon)

    def set_coords(
        self,
        key: tuple[str, float, float],
        lat: float,
        lon: float,
    ) -> None:
        """Store coordinates and refresh LRU order."""
        now = time.monotonic()
        self._entries[key] = (lat, lon, now)
        self._entries.move_to_end(key)
        while len(self._entries) > NAV_FIX_CACHE_MAX_ENTRIES:
            self._entries.popitem(last=False)

    def clear(self) -> None:
        """Remove all entries (e.g., between tests)."""
        self._entries.clear()


_fix_cache = CoordLookupCache()
_nav_cache = CoordLookupCache()


def get_fix_cache() -> CoordLookupCache:
    """Shared fix lookup cache instance."""
    return _fix_cache


def get_nav_cache() -> CoordLookupCache:
    """Shared nav lookup cache instance."""
    return _nav_cache


def clear_navigation_coord_caches() -> None:
    """Clear fix and nav coordinate caches (tests)."""
    _fix_cache.clear()
    _nav_cache.clear()

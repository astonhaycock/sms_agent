"""
Trail registry — maps trail IDs and aliases to trail data dicts.
Add new trails here; the agent tools pick them up automatically.
"""
from agent_router.trails.data.devils_garden import DEVILS_GARDEN
from agent_router.trails.data.zion import (
    ZION_OVERVIEW,
    ZION_CANYON,
    EAST_RIM,
    SOUTHWEST_DESERT,
    KOLOB_CANYONS,
)

_TRAILS = [
    DEVILS_GARDEN,
    ZION_OVERVIEW,
    ZION_CANYON,
    EAST_RIM,
    SOUTHWEST_DESERT,
    KOLOB_CANYONS,
]

# Build alias → trail lookup (lowercase)
_ALIAS_MAP: dict[str, dict] = {}
for _trail in _TRAILS:
    for _alias in _trail.get("aliases", []):
        _ALIAS_MAP[_alias.lower()] = _trail
    _ALIAS_MAP[_trail["id"].lower()] = _trail
    _ALIAS_MAP[_trail["name"].lower()] = _trail


def find_trail(query: str) -> dict | None:
    """Return the best-matching trail for a free-text query, or None."""
    q = query.strip().lower()
    # Exact alias match first
    if q in _ALIAS_MAP:
        return _ALIAS_MAP[q]
    # Substring match — prefer longer alias matches (more specific)
    best = None
    best_len = 0
    for alias, trail in _ALIAS_MAP.items():
        if alias in q or q in alias:
            if len(alias) > best_len:
                best = trail
                best_len = len(alias)
    return best


def list_trails() -> list[dict]:
    return _TRAILS


def expand_path(trail: dict, path: list[str]) -> str:
    """Convert a list of node codes to a human-readable path string."""
    if not path:
        return ""
    nodes = trail.get("nodes", {})
    return " → ".join(nodes.get(code, {}).get("name", code) for code in path)

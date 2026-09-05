"""Access to the application settings from the service layer.

`app/config.py` owns all environment variable reading, including the `HS_`
prefix and the bare name fallback. This module only re-exports that object and
adds one helper, so that a service can read a single value with a default.

Do not add environment variable logic here. It belongs in `app/config.py`.
"""

from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings

__all__ = ["Settings", "get_settings", "setting"]


def setting(name: str, default: Any = None) -> Any:
    """Return one setting value, or `default` if the setting is absent."""
    return getattr(get_settings(), name, default)

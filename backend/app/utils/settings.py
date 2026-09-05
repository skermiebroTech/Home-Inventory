"""Access to the application settings object.

`app/config.py` owns all environment variable reading, including the `HS_`
prefix and the bare name fallback. This module only finds the settings object
that `app/config.py` exports. It exists so that the service layer has one
import to change if the name of that export changes.

Do not add environment variable logic here. It belongs in `app/config.py`.
"""

from __future__ import annotations

from typing import Any


def get_settings() -> Any:
    """Return the application settings object.

    The function accepts either a `get_settings()` factory or a `settings`
    singleton in `app/config.py`.
    """
    import app.config as config

    factory = getattr(config, "get_settings", None)
    if callable(factory):
        return factory()
    settings = getattr(config, "settings", None)
    if settings is not None:
        return settings
    raise RuntimeError("app.config exports neither get_settings() nor settings")


def setting(name: str, default: Any = None) -> Any:
    """Return one setting value, or `default` if the setting is absent."""
    try:
        return getattr(get_settings(), name, default)
    except Exception:
        return default

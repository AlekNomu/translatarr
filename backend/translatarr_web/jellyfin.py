"""
translatarr_web.jellyfin
~~~~~~~~~~~~~~~~~~~~~~~~
Jellyfin API integration: trigger library refresh after subtitle generation.
"""

from __future__ import annotations

import logging
import urllib.request

logger = logging.getLogger("translatarr")


def refresh_library(settings: dict) -> bool:
    """Send a POST /Library/Refresh to Jellyfin to pick up new subtitle files.

    Returns True if the request succeeded, False otherwise (Jellyfin disabled,
    unreachable, or misconfigured — all handled silently).
    """
    if settings.get("jellyfin_enabled", "0") != "1":
        return False

    host = settings.get("jellyfin_host", "jellyfin")
    port = settings.get("jellyfin_port", "8096")
    api_key = settings.get("jellyfin_api_key", "")
    try:
        timeout = int(settings.get("jellyfin_http_timeout", "60"))
    except ValueError:
        timeout = 60

    url = f"http://{host}:{port}/Library/Refresh"
    req = urllib.request.Request(
        url,
        data=b"",
        headers={"Authorization": f'MediaBrowser Token="{api_key}"'},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status < 300
    except Exception as exc:
        logger.warning("Jellyfin library refresh failed: %s", exc)
        return False

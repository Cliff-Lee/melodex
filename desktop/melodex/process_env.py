from __future__ import annotations

import os
from collections.abc import Mapping

# Keep only ordinary OS/runtime variables that child processes commonly need.
# In particular, do not forward arbitrary API keys, tokens, cookies, provider
# credentials, or a parent PYTHONPATH into third-party code.
_CHILD_ENV_ALLOWLIST = (
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "USERPROFILE",
    "TMPDIR",
    "TMP",
    "TEMP",
    "SystemRoot",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TZ",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE",
)


def scrubbed_child_env(
    *,
    identifier_key: str,
    identifier: str,
    parent: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build a minimal environment for third-party provider/plugin processes."""

    source = os.environ if parent is None else parent
    env = {
        key: str(source[key])
        for key in _CHILD_ENV_ALLOWLIST
        if source.get(key)
    }
    env[str(identifier_key)] = str(identifier)
    return env

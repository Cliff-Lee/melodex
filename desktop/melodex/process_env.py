from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

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

    # Frozen macOS builds can run Python provider/extension workers without a
    # usable system CA path. Requests already ships certifi, so expose that CA
    # bundle to both requests and stdlib urllib/ssl children unless the user
    # explicitly supplied a certificate path.
    if not env.get("SSL_CERT_FILE"):
        try:
            import certifi

            ca_file = str(certifi.where() or "").strip()
            if ca_file and Path(ca_file).is_file():
                env["SSL_CERT_FILE"] = ca_file
                env.setdefault("REQUESTS_CA_BUNDLE", ca_file)
                env.setdefault("CURL_CA_BUNDLE", ca_file)
        except Exception:
            pass

    env[str(identifier_key)] = str(identifier)
    return env

# Navidrome / OpenSubsonic (experimental)

An **optional** Melodex MPP 1.0-preview provider for a music server you operate or are authorized to use. It is deliberately **not included** in `desktop/melodex/bundled_providers/` or the default enabled provider list.

## Development / installation

```bash
python -m pip install -e provider-sdk
melodex-provider validate desktop/bundled_provider_sources/opensubsonic_personal
melodex-provider doctor desktop/bundled_provider_sources/opensubsonic_personal --no-runtime
melodex-provider pack desktop/bundled_provider_sources/opensubsonic_personal
```

Install the resulting `.mdxprovider` using **Melodex → Sources → Install .mdxprovider**, in an isolated test profile. The doctor command uses static-only mode because the SDK runtime doctor calls authenticated search without supplying a user's private credentials. Check MPP subprocess functionality with the offline tests, and validate real server health/search/playback separately. The full SDK and desktop installation checks are still required; local mock tests alone do not prove compatibility.

Set your server URL, username and password in Sources. Secrets are delivered per request using the host's `_melodex_config` broker rather than being hardcoded into the manifest. HTTPS is required by default. For a trusted local HTTP server, explicitly enable the insecure-HTTP option. Do not use HTTP on an untrusted network.

Implemented: health/ping, track search, exact track lookup, on-demand stream URL resolution and refresh. Not implemented: full remote library sync, offline downloads, playlists, artist/album browse, or transcoding controls. Real Navidrome/desktop audible playback and seeking remain unverified.

Security note: classic Subsonic salted tokens are embedded in playback query strings. They must never appear in logs, diagnostics or screenshots. Never publish personal library credentials. The existing provider host-permission model is not a network sandbox: it permits a configured media origin at playback time; do not misrepresent declared localhost hosts as a universal restriction.

See `SOURCE_POLICY.md` for authentication and rights. R1-3B tests live at `desktop/tests/test_opensubsonic_r1_3b.py`. The experimental source is not bundled, installed or registered by default.


## R1-3C real-server transport qualification (manual, Ubuntu/macOS)

In the real Melodex checkout, with your own authorized Navidrome/OpenSubsonic
account, run:

```bash
export MELODEX_SUBSONIC_URL="https://your-music-server.example"
export MELODEX_SUBSONIC_USERNAME="your-username"
PYTHONPATH=desktop python desktop/tools/qualify_opensubsonic_live.py
```

The tool prompts for the password without echoing it to your terminal. Do not
put the password in shell history or commit it to GitHub. For a trusted
**local HTTP server only**, explicitly opt in with:

```bash
export MELODEX_SUBSONIC_ALLOW_HTTP=1
```

It checks authenticated health, search, exact lookup, stream resolution, and
whether a loopback playback-gateway request receives HTTP 206 for a byte range.
If no search results are found, set `MELODEX_SUBSONIC_QUERY` to an ordinary
term known to exist in your own library. The tool prints only coarse booleans,
not titles, account names, URLs or auth tokens. Success does **not** prove
sound-device output, full-track playback, resume, or seeking in Qt: those still
require hands-on verification in a packaged Melodex build.

The fake-server integration tests can run without credentials:

```bash
PYTHONPATH=desktop pytest -q \
  desktop/tests/test_opensubsonic_r1_3b.py \
  desktop/tests/test_opensubsonic_integration_r1_3c.py \
  desktop/tests/test_gateway_r1_3b.py
```

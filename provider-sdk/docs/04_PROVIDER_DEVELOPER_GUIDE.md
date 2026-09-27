# 4. Provider developer guide

## 4.1 The 15-minute path

A desktop Python provider needs:

```text
my-provider/
  manifest.json
  provider.py
  README.md
  LICENSE
  vendor/          # optional
```

Create it with:

```bash
melodex-provider init my-provider
melodex-provider doctor my-provider
```

## 4.2 Required semantic operations

A playback provider normally implements:

- `provider.info`
- `provider.health`
- `catalog.search`
- `catalog.get_track`
- `playback.resolve`

`playback.refresh` is optional and is intended for short-lived playback URLs.
Older v0.1 providers remain valid.

## 4.3 Normalize early

Convert provider-specific data into a small stable object:

```json
{
  "type": "track",
  "provider_id": "org.example.music",
  "provider_track_id": "opaque-id",
  "artist": "Example Artist",
  "title": "Example Track",
  "album": "Example Album"
}
```

The track ID is opaque. It can be a source ID, compound key, or stable hash of a
canonical detail URL.

## 4.4 Playback resources

Simple source:

```json
{
  "kind": "http",
  "url": "https://cdn.example.org/audio/123.mp3",
  "headers": {},
  "cookies": {},
  "seekable": true,
  "cache_policy": "session"
}
```

Source that requires request state:

```json
{
  "kind": "http",
  "url": "https://cdn.example.org/temporary/abc",
  "headers": {"Referer": "https://example.org/track/123"},
  "cookies": {"session": "opaque-provider-value"},
  "expires_at": "2026-09-27T14:30:00Z",
  "refresh_token": "opaque-refresh-state",
  "seekable": true,
  "cache_policy": "session"
}
```

The desktop Playback Gateway forwards the required state and preserves Range
requests for seeking.

## 4.5 Messy sources

Keep discovery and playback separate. A provider may internally:

1. search an API or HTML page;
2. follow one or more detail pages;
3. normalize inconsistent metadata;
4. obtain an authorized temporary playback URL;
5. return a normalized PlaybackResource.

Use `melodex_provider_sdk.WebSession` for cookies, redirects, retries, gzip and
rate limiting. Vendor Beautiful Soup or lxml when CSS/XPath parsing is required.

## 4.6 Dependencies

Pure-Python dependencies can be bundled under `vendor/`. Platform-specific
standalone executables can use entrypoint keys such as `macos-arm64`,
`windows-x86_64` or `linux-x86_64`.

## 4.7 Security and permissions

Use documented APIs or access methods for which the user/provider has
permission. Do not put credentials in catalog metadata or LLM context. The SDK
intentionally omits DRM circumvention, CAPTCHA solving and access-control bypass
helpers.

## 4.8 Test and package

```bash
melodex-provider validate my-provider
melodex-provider doctor my-provider
melodex-provider pack my-provider
```

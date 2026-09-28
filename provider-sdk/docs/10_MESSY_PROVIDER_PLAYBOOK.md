# Messy provider playbook

A "messy" provider is one whose authorized playback path is not a single clean
JSON API call. Source-specific complexity stays inside the provider.

## Recommended pipeline

```text
search → candidate → detail → normalize → playback.resolve → PlaybackResource
```

For short-lived resources:

```text
queue wait → expires_at approaches → playback.refresh → fresh resource
```

## Common patterns

### HTML search pages

Prefer a real HTML parser and stable semantic anchors. Keep multiple fallbacks
for fields known to vary. Regex is a last fallback for small embedded fragments.

### Relative links

Use `absolute_url(base, value)` before storing detail or media URLs.

### Missing IDs

Use `opaque_id(canonical_url)` or a compound source key.

### Sessions and cookies

Keep discovery session state inside the provider. Return only cookies required
for the media request.

### Referer or custom headers

Put required media-request headers in the PlaybackResource. QMediaPlayer receives
only a loopback URL from the Playback Gateway.

### Redirects and CDNs

Declare expected API/media/CDN hosts in `permissions.network_hosts`. The desktop
gateway rejects a redirect outside the declared host set for external providers.

### Expiring URLs

Set `expires_at`. If refresh requires provider state, include an opaque
`refresh_token` and implement `playback.refresh`. Melodex falls back to a fresh
`playback.resolve` when refresh is unsupported.

## Deliberate boundaries

The public SDK does not provide DRM circumvention, CAPTCHA solving, anti-bot
evasion, credential harvesting, or access-control bypasses.

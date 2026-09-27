# Playback Gateway

Some authorized media sources require HTTP request state that QMediaPlayer does
not conveniently expose. The desktop Playback Gateway bridges that mismatch.

```text
provider PlaybackResource
  URL + headers + cookies
          ↓
127.0.0.1 Playback Gateway
          ↓
QMediaPlayer
```

The gateway:

- binds only to `127.0.0.1`;
- uses an unguessable token for each registered resource;
- forwards provider headers and the supplied playback cookies;
- follows ordinary HTTP redirects only after validating each next destination;
- forwards Range requests for seeking;
- forwards Content-Range, Content-Type and related response headers;
- checks declared provider hosts for external provider resources;
- treats an external provider with an empty `network_hosts` list as having no
  permission to make playback network requests.

Redirect destinations are checked before Melodex sends the next request, so
provider-supplied headers and cookies are not forwarded to an undeclared host.

## Refresh

`expires_at` lets Melodex identify a nearly stale resource. Desktop playback can
call optional `playback.refresh`; ExternalProvider falls back to
`playback.resolve` for v0.1 compatibility.

## Current boundary

v0.2 primarily targets normal HTTP audio resources. HLS without special request
state can still be passed directly to the media framework. Protected HLS segment
rewriting is not part of this release.

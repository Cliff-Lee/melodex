# OpenSubsonic source and rights policy

## Access and authentication
The provider connects only to the explicitly configured Subsonic-compatible server. It uses documented `ping`, `search3`, `getSong` and `stream` operations and MD5 password-plus-random-salt Subsonic token authentication. It does **not** bypass server authentication or authorization. A valid authorized account is required. No credentials are supplied with the source.

## Network permissions
Requests use a user-selected HTTP(S) server URL; HTTPS is mandatory unless the user explicitly allows insecure HTTP for a trusted server. The provider rejects redirects for authenticated API calls. Stream redirects may be blocked by the Melodex Playback Gateway host policy. The current core's dynamic playback host allowance is **not** a complete sandbox, and needs separate security review.

## Rights
The user is responsible for having rights to the media served by the configured server. This provider does not source public music or grant distribution rights. Media streams are for authorized listening.

## Data handling
The provider doesn't write passwords or a local music cache. It does not download tracks for offline use. Stream requests use per-request authentication salts; tokens in query strings are sensitive and must never be logged. Provider-hosted server logs and proxy logs are governed by the server administrator.

## Stability
Experimental: mock-server/JSON-RPC tests available; real authenticated server tests, audible playback, seeking and desktop SDK qualification must be performed before bundling or release. Not registered in the public provider registry.

# API Security

## Default: loopback

The desktop control bridge is intended to run on loopback by default.

External devices should only be allowed when LAN access is intentional.

## Bearer tokens

Treat Bridge and MCP bearer tokens as passwords.

QR pairing uses a one-time code that expires after two minutes. Each paired phone receives a separate token. The phone encrypts its saved Bridge token with Android Keystore; the desktop stores only the token digest in a user-only file and supports revocation per phone.

Do not include tokens in logs, screenshots, issue reports or model prompts.

## Media query token

The media endpoint may accept a token in the URL because some media players cannot attach Authorization headers.

Do not treat token-bearing media URLs as permanent track IDs, and do not paste them into public logs or chats.

## LAN / remote access

Pairing and playback use the existing local Bridge HTTP connection. Use only a trusted local network; plain HTTP bearer tokens are not appropriate across untrusted networks. Use a trusted VPN or TLS reverse proxy for remote access.

## OpenAPI document

`/openapi.json` is public on the bridge by design. It describes operations but contains no token or private user data.

## Model API credentials

Model-service credentials belong to the outbound LLM configuration, not the local Melodex control API. Do not place them in provider metadata, plugin manifests, model context or repositories.

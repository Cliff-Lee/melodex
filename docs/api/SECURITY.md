# API Security

## Default: loopback

The desktop control bridge is intended to run on loopback by default.

External devices should only be allowed when LAN access is intentional.

## Bearer tokens

Treat Bridge and MCP bearer tokens as passwords.

Do not include them in logs, screenshots, issue reports or model prompts.

## Media query token

The media endpoint may accept a token in the URL because some media players cannot attach Authorization headers. Query-token authentication is accepted only by `/v1/media`; other protected endpoints require `Authorization: Bearer …`.

Do not treat token-bearing media URLs as permanent track IDs, and do not paste them into public logs or chats.

## LAN / remote access

Plain HTTP bearer tokens are not appropriate across untrusted networks. Use a trusted VPN or TLS reverse proxy for remote access.

## OpenAPI document

`/openapi.json` is public on the bridge by design. It describes operations but contains no token or private user data.

## Model API credentials

Model-service credentials belong to the outbound LLM configuration, not the local Melodex control API. Do not place them in provider metadata, plugin manifests, model context or repositories.


## Playback metadata redaction

Public Bridge catalog/control JSON removes provider playback headers, cookies, refresh tokens, local paths and raw upstream playback URLs.

Resolved playable tracks expose a Bridge-owned media URL instead. Ordinary remote streams may still be redirected by `/v1/media`; custom upstream request-state proxying is not yet complete.

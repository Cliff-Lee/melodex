# Troubleshooting

## Flow says deep analysis is unavailable

Install FFmpeg and restart Melodex. Flow still works in reduced mode without it.

## Jamendo says a client ID is required

Create a Jamendo developer application and paste its client ID into **Sources → Jamendo settings**.

## A provider will not install

Validate it with the Provider SDK:

```bash
melodex-provider validate path/to/provider
```

## Android cannot reach the Bridge

- use the desktop machine's LAN IP, not `127.0.0.1`;
- ensure the Bridge was started in LAN mode;
- check the firewall;
- keep phone and server on the same network;
- confirm the bearer token exactly.

## LLM connection fails

Check endpoint, model name and API key. For OpenWebUI in Docker, ensure the endpoint is reachable from the machine running Melodex.

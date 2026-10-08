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

- keep the phone and computer on the same trusted Wi-Fi/LAN;
- check that the Bridge is in LAN mode and allow it through the computer's firewall;
- refresh the desktop QR code if it was open for more than two minutes or has already been scanned;
- if using Advanced setup, check the Bridge URL and current session token;
- guest Wi-Fi client isolation can block devices even when they show the same network.

## LLM connection fails

Check endpoint, model name and API key. For OpenWebUI in Docker, ensure the endpoint is reachable from the machine running Melodex.


## A third-party provider or extension is failing

Open **Sources** and check whether the plugin shows **CONFIG NEEDED**, a disabled state, or an extension health error.

For a support report, use:

```text
Sources
→ Show power tools
→ Export diagnostics…
```

The export is designed to omit credentials, local library paths, stream/playback URLs, headers and cookies. Review it before sharing.

See [Support](../SUPPORT.md) for what to include in an issue.

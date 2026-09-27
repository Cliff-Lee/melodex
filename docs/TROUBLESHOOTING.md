# Troubleshooting

## Flow says deep analysis is unavailable
Melodex still works in reduced mode. Install/enable FFmpeg if you want deeper local audio analysis.

## Internet Archive search works but playback takes several seconds
This can be normal. The provider resolves an Archive item to a playable representation and may route it through the local Playback Gateway. Very large aggregate files can take noticeably longer.

If playback never begins, test a smaller Archive item and confirm normal local playback works.

## Jamendo says a client ID is required
Create a Jamendo developer application and paste your client ID into **Sources -> Jamendo settings...**.

## User Stream does not play
- confirm the URL is a direct playable HTTP(S) audio/radio endpoint;
- check that the endpoint is reachable;
- re-check the URL for expired/private tokens;
- Melodex does not discover private endpoints or bypass authentication.

## A provider will not install

```bash
melodex-provider validate path/to/provider
melodex-provider doctor path/to/provider
```

## Linux AppImage will not launch

```bash
chmod +x Melodex-Linux-x86_64.AppImage
./Melodex-Linux-x86_64.AppImage
```

Run from a terminal to capture the error.

## Android cannot reach the Bridge
- use the desktop machine's LAN IP, not `127.0.0.1`;
- ensure the Bridge was started in LAN mode;
- check the firewall;
- keep phone and server on the same network;
- confirm the bearer token exactly.

## LLM connection fails
Check endpoint, model name and API key. For OpenWebUI in Docker, ensure the endpoint is reachable from the relevant machine/container.

## A resolver match is wrong
Open **Match** and use **Wrong match**, **Prefer**, or **Reset memory**.

## More help
- [User Manual](manuals/Melodex_User_Manual_v0.2.pdf)
- [Power User Manual](manuals/Melodex_Power_User_Manual_v0.2.pdf)
- [FAQ](FAQ.md)

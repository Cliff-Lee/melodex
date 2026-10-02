# Source policy — NicheDB Radio

This provider does not copy, host, download, or redistribute radio audio.

Discovery and normalized station metadata come from NicheDB's public read API. NicheDB's radio collection is populated from the Radio Browser community directory and refreshed on NicheDB's schedule. Playback connects Melodex directly to the stream URL carried by the selected NicheDB station item.

The provider only exposes stations that include a stream URL and are not marked offline by NicheDB. Stream availability can still change between discovery and playback.

Station programming, stream rights, geographic restrictions and upstream terms remain controlled by each station/network. Offline download is disabled.

References:

- <https://nichedb.dev/c/radio>
- <https://nichedb.dev/docs/api>
- <https://www.radio-browser.info/>

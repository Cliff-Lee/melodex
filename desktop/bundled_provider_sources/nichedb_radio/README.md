# NicheDB Radio provider

Melodex provider for NicheDB's daily-refreshed internet-radio catalogue.

This 0.1.2 build uses Melodex's bundled `requests`/CA bundle for HTTPS rather
than Python's bare `urllib`, which avoids certificate-chain failures in
packaged macOS builds.

Search examples:

- `jazz`
- `BBC`
- `ambient`
- `popular`
- `genre:ambient`
- `country:gb`
- `lang:english`
- `codec:mp3`

No account or API key is required for normal use.

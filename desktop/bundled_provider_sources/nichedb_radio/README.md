# NicheDB Radio provider

Melodex provider for NicheDB's daily-refreshed internet-radio catalogue.

This 0.1.2 test build uses Melodex's bundled `requests`/`certifi` HTTPS stack to
avoid the macOS packaged-app certificate-chain problem seen with Python `urllib`.

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

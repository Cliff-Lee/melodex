# Legal / Open Reference Sources for Provider Development

**Last reviewed:** 2026-09-28

These are useful development/reference sources, not a blanket statement that every file, stream, jurisdiction or use is permitted.

Always check current API terms and preserve item-level rights/provenance where relevant.

## Jamendo

Good for a real JSON music API with user-supplied developer credentials and per-track Creative Commons metadata.

Current Jamendo API terms say API content is published under Creative Commons licences, require artist/Jamendo attribution and a backlink, and distinguish non-commercial API use from commercial use.

- Developer portal: https://developer.jamendo.com/
- API terms: https://devportal.jamendo.com/api_terms_of_use

Melodex's built-in Jamendo reference provider intentionally declares no offline-download capability.

## Radio Browser

Useful for live radio directory search and continuous playback.

Radio Browser asks clients to use available mirrors, send a meaningful User-Agent and use its station-click endpoint when a user selects/plays a station.

- API: https://api.radio-browser.info/
- Documentation: https://docs.radio-browser.info/

The openness of the directory/API does not confer redistribution rights over the programming broadcast by individual stations.

## LibriVox

Useful for long-form/chaptered audio.

LibriVox states that its recordings are public domain in the United States and specifically tells users elsewhere to check local copyright status.

Its September 16, 2026 API update asks clients to use bounded/paged requests and separate requests by several seconds.

- Public-domain guidance: https://librivox.org/pages/public-domain/
- API update: https://librivox.org/2026/09/16/librivox-api-update/

## MusicBrainz

Useful for canonical music identity and structured metadata.

MusicBrainz asks public API clients to use a meaningful User-Agent and normally stay around one request per second per IP.

Core MusicBrainz database data is CC0; supplementary data has separate licensing.

- API: https://musicbrainz.org/doc/MusicBrainz_API
- Rate limiting: https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting
- Data licensing: https://musicbrainz.org/doc/About/Data_License

## Wikimedia Commons

Useful for artwork/image enrichment and testing per-file provenance.

Commons files do not all share one licence. Reuse should preserve file-level creator/licence/source information and account for non-copyright restrictions where relevant.

- API overview: https://www.mediawiki.org/wiki/API:Main_page
- Content reuse: https://www.mediawiki.org/wiki/Wikimedia_APIs/Content_reuse
- Commons reuse guidance: https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia

## Internet Archive

Useful for heterogeneous item/file metadata and collections with several media representations.

Rights statements vary by item; public availability is not a blanket copyright assertion.

- Developer docs: https://archive.org/developers/

Melodex keeps the current Internet Archive integration source separate from Core rather than treating every archive item as automatically installable/offline-safe.

## Freesound

Potentially useful for search, tags, previews and Creative Commons licence handling.

It is not currently one of Melodex's canonical installable reference packages.

Review API/commercial-use and per-item licence requirements before building/distributing an integration.

- API docs: https://freesound.org/docs/api/

## Reproducible testing

Prefer local fixtures for unit tests.

Fixtures can simulate changing JSON/HTML/XML, redirects, Referer requirements, cookies, Range requests and expiring URLs without making CI depend on a live upstream service or embedding bypass behavior into Melodex.

## Project rule

“Legal/open reference source” means **we can explain the documented access/rights model used by the example**.

It does not mean Melodex guarantees every possible downstream use in every jurisdiction.

# Source Policy — MusicBrainz

**Last reviewed:** 2026-09-28

Primary sources:

- https://musicbrainz.org/doc/MusicBrainz_API
- https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting
- https://musicbrainz.org/doc/About/Data_License

Access method: MusicBrainz Web Service `/ws/2`.

Authentication: no API key is required for ordinary public read requests.

## Client behavior

MusicBrainz currently asks clients to:

- send a meaningful User-Agent identifying the application;
- keep normal public API traffic to about one request per second per IP unless separately agreed;
- behave considerately under throttling/service load.

The reference extension uses a descriptive User-Agent, a little over one second between calls, bounded timeouts and no aggressive retry loop.

## Rights

MusicBrainz documents different licensing for different data classes:

- core database data is CC0;
- supplementary data has separate licensing.

The reference extension preserves MusicBrainz provenance and does not claim that every returned field has identical licensing.

Commercial users should review current MetaBrainz API/commercial terms rather than assuming the public non-commercial web-service policy applies unchanged.

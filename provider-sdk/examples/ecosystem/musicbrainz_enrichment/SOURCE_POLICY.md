# Source Policy — MusicBrainz

Source: https://musicbrainz.org/

Access method: MusicBrainz Web Service `/ws/2`.

Authentication: no API key for read requests.

Client behaviour:

- descriptive User-Agent;
- at most about one request/second per IP unless separately agreed;
- bounded timeout;
- no aggressive retry loop.

Rights:

- MusicBrainz core database data is CC0;
- supplementary data has separate licensing;
- this example records "MusicBrainz" provenance rather than claiming every
  returned field has identical licensing.

Commercial use should review current MetaBrainz API/commercial terms.

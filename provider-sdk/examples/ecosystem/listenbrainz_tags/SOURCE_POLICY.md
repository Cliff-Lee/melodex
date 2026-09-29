# Source Policy — ListenBrainz Tags Example

## Upstream

- API: `https://api.listenbrainz.org/1/metadata/recording/`
- Authentication: none for the recording metadata lookup used here.
- Required input: MusicBrainz recording MBID.
- Requested enrichment data: tag metadata only (`inc=tag`).
- Health check: `GET /1/status/service-status`, used only when the user explicitly tests plugin health.

## Rights and provenance

ListenBrainz states that user listen data and text are public under CC0. The wider metadata response can also incorporate MusicBrainz-derived data, whose licensing depends on the field/dataset. This example emits only tag labels/counts from the ListenBrainz tag block and records a conservative MetaBrainz licensing note in provenance rather than overclaiming a single licence for the entire response.

## Privacy

This plugin does not send a username, listening history or user token. It sends only the MusicBrainz recording ID being enriched.

## Caching

The response requests a one-day TTL. Tags are community-derived and may change.

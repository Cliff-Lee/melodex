# Cover Art Archive Artwork Example

A Melodex v0.1 `artwork.lookup` extension for album/track cover art.

It consumes `musicbrainz_release_id` or `musicbrainz_release_group_id`, so it composes naturally after the MusicBrainz identity extension. It prefers images marked as front covers and returns provenance pointing to the Cover Art Archive API record.

This is deliberately an **artwork** plugin, not a metadata or playback provider.

# Melodex Artist Visuals

This stage extends Rich Now Playing with two visual/music-knowledge features:

1. **Wikimedia / Wikidata artist photographs**
2. **Release timeline / album-cover wall**

## Overview

Melodex keeps playback-source resolution separate from metadata and visuals.
A currently playing track can therefore be assembled from independent sources:

- audio: local / provider / resolver
- identity: MusicBrainz
- cover art: embedded art / provider / Cover Art Archive
- artist photo: Wikimedia Commons via Wikidata
- lyrics: local embedded tags / `.lrc` / `.txt`

## Artist photographs

When MusicBrainz artist links contain a Wikidata URL, Melodex looks up the Wikidata entity and checks for image claim `P18`.
That file name is turned into a Wikimedia Commons `Special:FilePath` URL and cached locally.

Returned fields include:

- `path`
- `source`
- `source_url`
- `attribution`
- `wikidata_qid`
- `filename`

If no Wikidata link or image exists, Melodex simply omits the artist photo.

## Release timeline / album wall

Melodex uses MusicBrainz release groups for the identified artist and collects:

- release-group id
- title
- primary type
- secondary types
- first release date / year
- a Cover Art Archive thumbnail URL
- cached cover path when available

The Now Playing page renders this as a release timeline with a compact cover wall.

## Notes

- Wikimedia image licensing metadata is not fully normalised in this first version; Melodex currently stores a simple attribution string and source URL.
- Artist photos are intentionally optional and never block playback.
- Discography lookups are cached and independent from audio providers.

## Next logical step

After this stage, the most natural visual upgrade is:

- waveform / mini-spectrum visualisation
- optional ListenBrainz / Last.fm enrichment
- click-through artist/release exploration pages

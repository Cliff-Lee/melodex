# Wikimedia artist-photo attribution

Melodex artist photos are optional visual enrichment. When a MusicBrainz artist links to Wikidata and Wikidata provides a Commons image (`P18`), Melodex now resolves the actual Wikimedia Commons file page and retrieves file-level metadata through the MediaWiki `imageinfo` API with `extmetadata`.

For an image, Melodex records when available:

- creator / Artist;
- Credit;
- explicit Attribution string;
- licence short name;
- licence URL;
- usage terms;
- whether attribution is required;
- whether the file is marked copyrighted;
- the Wikimedia Commons file-description URL;
- the downloaded display image URL.

The visible Now Playing artist-photo credit links back to the Commons file page and links the licence when a licence URL is supplied.

## Why this matters

Wikimedia Commons files are not all under the same licence. Some are public domain, while others require attribution and/or share-alike terms. A generic "Wikimedia Commons" label is therefore not sufficient for every file.

Melodex does not relicense Commons images. The file-level licence and attribution supplied by Commons remain controlling.

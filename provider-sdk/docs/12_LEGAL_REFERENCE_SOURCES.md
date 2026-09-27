# Legal reference sources for provider development

These are useful reference categories, not a blanket statement that every file
or use is permitted. Check current API terms and the rights/licence metadata of
each item.

## Jamendo

Already used by Melodex as a clean JSON/API reference source with a user-supplied
client ID and per-track licence/attribution metadata.

Developer portal: https://developer.jamendo.com/

## Wikimedia Commons audio

Useful for testing search, file metadata, direct media URLs and per-file licence
attribution.

API: https://www.mediawiki.org/wiki/API:Main_page
Reuse guidance: https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia

## Internet Archive audio

Useful for heterogeneous item/file metadata and collections with several media
representations. Rights statements vary by item.

Developer docs: https://archive.org/developers/

## LibriVox

Public-domain spoken-word material is useful for long-form audio and chaptered
catalogues.

API: https://librivox.org/api/info

## Freesound

Useful for search, tags, previews and Creative Commons licence handling. Check
API and commercial-use terms for the intended application.

API docs: https://freesound.org/docs/api/

## Reproducible testing

Prefer local fixtures that simulate changing HTML, redirects, required Referer
headers, cookies, Range requests and expiring URLs. This tests the provider
architecture without embedding service-specific bypass logic in Melodex.

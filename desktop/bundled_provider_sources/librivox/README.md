# LibriVox bundled provider

Melodex exposes LibriVox as a focused public-domain audiobook source.

The provider searches the Internet Archive `librivoxaudio` collection and resolves
selected books to hosted MP3 files. This deliberately avoids issuing interactive
search traffic to the volunteer-hosted LibriVox API, whose September 2026 guidance
asks API clients to reduce request pressure and space requests out.

LibriVox remains the content/source identity. Internet Archive is the catalogue
index and media host used by this integration.

Rights note: LibriVox recordings are public domain in the United States. Users
should check copyright status in their own jurisdiction.

Version 0.1.5 also permits Internet Archive's regional `*.archive.org` media CDN hosts, so legitimate redirects such as `*.ca.archive.org` remain playable through Melodex's secure playback gateway.

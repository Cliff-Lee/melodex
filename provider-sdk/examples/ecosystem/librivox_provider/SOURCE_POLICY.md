# Source Policy — LibriVox

Source: https://librivox.org/

LibriVox states that its recordings are public domain in the United States and
welcomes third-party reuse.

The official API is used for discovery. Audio section URLs are supplied by
LibriVox and generally hosted by Internet Archive.

The September 16, 2026 API update:

- caps a request at 500 records;
- asks developers to page with offsets;
- asks clients to separate requests by several seconds.

This example uses small limits and never attempts whole-catalog bulk download.

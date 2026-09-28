# Source Policy — LibriVox

**Last reviewed:** 2026-09-28

Primary sources:

- https://librivox.org/pages/public-domain/
- https://librivox.org/2026/09/16/librivox-api-update/

LibriVox states that its recordings are public domain in the United States and welcomes third-party reuse.

LibriVox also explicitly warns that public-domain status can differ by country and advises users outside the United States to check the copyright status applicable where they are.

The official API is used for discovery. Audio section URLs are supplied by LibriVox and are commonly hosted by Internet Archive.

## Current API guidance

LibriVox's September 16, 2026 API update states that:

- the API normally returns 50 records per request;
- the maximum requested limit is 500 records;
- full-catalog users should page with offsets (and can use `since` for incremental updates);
- developers should separate requests by several seconds rather than send bursts.

The reference provider uses small limits, a paced request loop, and does not attempt a whole-catalog bulk download.

# Source Policy — Wikimedia Liner Notes

## Upstream

- Wikidata entity JSON: `https://www.wikidata.org/wiki/Special:EntityData/{QID}.json`
- English Wikipedia page summary: `https://en.wikipedia.org/api/rest_v1/page/summary/{title}`
- Authentication: none.
- Only the Wikidata QID for the currently playing artist is sent.

## Rights and attribution

Wikidata structured data is CC0. Wikipedia article text is reusable under the licence shown by the Wikimedia project, commonly CC BY-SA. Every returned card links to the source article and identifies Wikipedia contributors / Wikidata in provenance.

This plugin uses the short page-summary extract; it does not scrape full articles.

## Caching

Context responses request a seven-day TTL. Attribution/source information is cached alongside the text.

# Source and Rights Policy

**Project policy, not legal advice.**

A plugin being technically possible does not automatically make it appropriate for the public Melodex registry.

## Ask four separate questions

1. Is the **API** free to call?
2. Is the **data** openly licensed?
3. Is the **media** openly licensed or public domain?
4. Does the service permit the intended feature: streaming, caching, download, redistribution or commercial use?

Those answers may be different.

## Strong reference-source patterns

### Radio Browser

Useful for search/playback examples. Respect mirror discovery, descriptive User-Agent guidance and station-click reporting. The directory being open does not make station programming Melodex-owned content.

### LibriVox

Excellent public-domain audiobook example. LibriVox recordings are public domain in the United States and the project welcomes third-party reuse. Be considerate of the API and avoid rapid bulk crawling.

### MusicBrainz

Excellent identity/metadata example. Use a meaningful User-Agent and respect current rate limits. MusicBrainz core database data is CC0; supplementary data may have different terms.

### Wikimedia Commons

Excellent artwork/provenance example. **Each file has its own licence and attribution requirements.** Preserve creator, licence, source page and other relevant metadata rather than assuming "Wikimedia = public domain."

## Conditional examples

Some services have useful APIs but stricter terms.

For example, a source may:

- require a developer key;
- restrict commercial use;
- require attribution/backlinks;
- forbid offline caching;
- return content whose rights vary per item.

Those restrictions belong in `SOURCE_POLICY.md` and in the plugin's declared behavior.

## What not to ship merely because scraping works

Do not treat a provider as an official/reference integration solely because a website is public, HTML can be scraped, a media URL can be discovered, or another player has an addon.

Prefer documented APIs and a clear permission/licence basis.

## Required source-policy questions

A public plugin should answer:

```text
What source is used?
What API/access method is used?
What permits this use?
API key required?
Rate limits?
Caching allowed?
Offline/download allowed?
Commercial restrictions?
Attribution required?
Rights vary per item?
```

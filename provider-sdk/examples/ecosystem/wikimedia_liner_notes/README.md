# Wikimedia Liner Notes

A Melodex v0.1 `context.lookup` extension that adds a short, sourced encyclopedic note to Now Playing.

The extension expects a Wikidata QID in the Melodex entity reference. It:

1. reads the English Wikipedia sitelink from Wikidata;
2. requests Wikipedia's page-summary endpoint;
3. returns the summary as a Context text card with source/licence attribution.

If no Wikidata link or English Wikipedia page is available, the plugin simply returns no card.

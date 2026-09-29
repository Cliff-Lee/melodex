# Source Policy — Public Domain Lyrics Example

## Source model

This extension makes no network requests. A tiny sample corpus is bundled under `fixtures/catalog.json` solely to exercise the Melodex `lyrics.lookup` contract.

The examples are historical texts published in the eighteenth/nineteenth centuries. Each item records a human-readable attribution, a source URL for inspection, and a conservative rights note.

## Rights boundary

This example intentionally does **not** use a modern public lyrics API merely because it is technically accessible. API access and lyric-text redistribution rights are different questions.

The plugin source code is MIT licensed. The bundled sample text is treated as public-domain historical source material; users distributing a broader lyrics plugin remain responsible for the rights and terms of their own source.

## Privacy / permissions

- no network access;
- no local-file access;
- no credentials;
- no browser authentication.

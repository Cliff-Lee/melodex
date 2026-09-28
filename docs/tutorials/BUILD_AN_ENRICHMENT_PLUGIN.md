# Tutorial — Build an Enrichment Plugin

Use this path if your service provides **knowledge about music** rather than playback.

Current experimental capability methods:

```text
identity.resolve
metadata.enrich
artwork.lookup
lyrics.lookup
```

## 1. Install the SDK

From the Melodex repository:

```bash
cd provider-sdk
python -m pip install -e '.[dev]'
```

This installs two developer CLIs:

```text
melodex-provider
melodex-extension
```

## 2. Create one small extension

Example artwork extension:

```bash
melodex-extension init my-artwork \
  --id org.example.artwork \
  --name "Example Artwork" \
  --capability artwork
```

Generated structure:

```text
my-artwork/
├── capabilities.json
├── plugin.py
├── README.md
├── SOURCE_POLICY.md
├── LICENSE
└── vendor/
```

## 3. Understand capabilities.json

```json
{
  "schema_version": "0.1",
  "extension_id": "org.example.artwork",
  "name": "Example Artwork",
  "version": "0.1.0",
  "entrypoints": {
    "python": "plugin.py"
  },
  "permissions": {
    "network_hosts": [],
    "local_files": false,
    "browser_auth": false
  },
  "contracts": [
    {
      "capability": "artwork",
      "contract_version": "0.1",
      "method": "artwork.lookup"
    }
  ]
}
```

Keep permissions honest and minimal.

## 4. Receive an EntityRef

Melodex calls the extension with normalized identity/hints:

```json
{
  "schema_version": "0.1",
  "capability": "artwork",
  "subject": {
    "entity_type": "artist",
    "canonical_ids": {
      "musicbrainz_artist_id": "..."
    },
    "hints": {
      "name": "Example Artist"
    }
  }
}
```

Canonical IDs are stronger evidence than display-text hints.

## 5. Return provenance

Example asset:

```json
{
  "url": "https://example.org/image.jpg",
  "role": "portrait",
  "score": 0.9,
  "provenance": {
    "source_extension_id": "org.example.artwork",
    "source_url": "https://example.org/image/123",
    "retrieved_at": "2026-09-28T00:00:00Z",
    "license": "CC BY-SA 4.0",
    "attribution": "Example Photographer"
  }
}
```

The origin and rights information should survive normalization.

## 6. Validate before testing Melodex

```bash
melodex-extension validate my-artwork
melodex-extension doctor my-artwork
```

`doctor` checks the descriptor and Python entrypoint without requiring a live network request.

## 7. Pack it

```bash
melodex-extension pack my-artwork
```

This creates:

```text
my-artwork.mdxplugin
```

## 8. Install it

In Melodex:

```text
Sources
→ Power tools
→ Install .mdxplugin…
```

Installed capability extensions appear below playback sources. They can be enabled, disabled or removed independently.

## 9. Fail independently

If artwork fails, playback should still work. If lyrics time out, metadata should still appear.

Do not make one capability depend unnecessarily on another capability extension being installed.

## 10. Test with fixtures

Save representative upstream API responses and test normalization offline.

Keep live-network tests optional because upstream outages and rate limits are not unit-test failures.

## Reference implementations

- `provider-sdk/examples/ecosystem/musicbrainz_enrichment/`
- `provider-sdk/examples/ecosystem/wikimedia_artwork/`

## Design reference

- [Capability reference](../developers/05_CAPABILITY_REFERENCE.md)
- [Capability Broker](../developers/16_CAPABILITY_BROKER.md)
- [Composition and provenance](../developers/06_COMPOSITION_AND_PROVENANCE.md)

# Melodex Provider SDK

A source-neutral provider protocol and developer SDK for **Melodex**.

> Melodex owns playback, Flow, taste, queueing and LLM control. Providers can supply
> catalog/playback access or narrower source-side discovery capabilities such as recommendations.

## Status

**SDK v0.9.0 / MPP 1.0 preview.**

The SDK/tooling is usable today, but the package remains 0.x and MPP 1.0 is still a **preview compatibility target**, not a frozen final protocol.

For the project's exact implemented/experimental/planned security and stability picture, see [Status, stability and trust](../docs/developers/00_STATUS_AND_STABILITY.md).

Melodex now has two package types:

```text
.mdxprovider   catalog/playback providers
.mdxplugin     identity/metadata/artwork/lyrics/context/local-intelligence extensions
```

## Fastest start

If you are new to the ecosystem, use the **[5-minute developer quickstart](../docs/DEVELOPER_QUICKSTART.md)**.

## Provider quick start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
melodex-provider init my-provider
melodex-provider validate my-provider
melodex-provider doctor my-provider
melodex-provider pack my-provider
```

Capability extension:

```bash
melodex-extension init my-artwork --capability artwork
melodex-extension validate my-artwork
melodex-extension doctor my-artwork
melodex-extension pack my-artwork
```

Context extensions use `context.lookup` to return sourced text/list/fact cards that Melodex can render in Rich Now Playing without plugin-specific GUI code.

Local-intelligence extensions use `library.suggest`. Melodex brokers a sanitized local-library snapshot with ephemeral refs, Flow features and coarse taste signals; plugins do not need direct access to the user's music folders or taste database.

Network-backed extensions may optionally declare the v0.1 `extension.health` method. This is lifecycle metadata rather than an enrichment capability; extensions that omit it remain compatible and use Melodex's process-check fallback. See the experimental extension contract reference for the request/response schema.

Registry maintenance:

```bash
melodex-registry validate registry/registry.json
melodex-registry summary registry/registry.json
melodex-registry verify-packages registry/registry.json --packages registry/packages
melodex-registry validate-reviews registry/registry.json --reviews registry/reviews
```

## Clean core, messy edge

Providers may deal internally with JSON APIs, HTML, XML, redirects, detail pages,
sessions or temporary CDN URLs. Melodex only needs normalized catalog items and
normalized playback resources.

```text
source-specific discovery
        ↓
provider adapter
        ↓
artist / title / album / opaque track id
        ↓
playback.resolve
        ↓
URL + optional headers/cookies/expiry
        ↓
Melodex Playback Gateway
        ↓
QMediaPlayer
```

## Declared configuration

Both `.mdxprovider` and `.mdxplugin` packages can declare simple user configuration fields:

```json
"configuration": [
  {"key": "api_token", "label": "API token", "type": "secret", "required": true},
  {"key": "region", "label": "Region", "type": "string"}
]
```

The current field types are `string`, `secret` and `boolean`. Melodex renders the configuration UI and supplies only those declared values to the plugin under the reserved `_melodex_config` request parameter.

Do not put actual credentials in manifests, packages, fixtures or registry metadata.

## Provider doctor

`melodex-provider doctor` checks the manifest, README, licence, `SOURCE_POLICY.md` and the Python entrypoint. Runtime checks are capability-aware: it calls `catalog.search` only when `search` is declared and checks `playback.resolve` only when a search result exists for a playback-capable provider. Recommendation-only providers can therefore be validated without pretending to implement search.

The generated provider scaffold includes all three documentation files so a first-time developer starts from the same public-release expectations used by the registry.

## Vendored dependencies

A Python provider may ship a `vendor/` directory. Melodex adds it to the provider
process `PYTHONPATH`, so a provider can remain self-contained without installing
packages into the user's Melodex environment.

The SDK also offers a small standard-library `WebSession` helper for cookies,
redirects, retries, gzip, rate limiting, relative URLs and JSON/XML responses.
Complex HTML parsers can be vendored per provider.

## Documentation

- [Provider developer guide](docs/04_PROVIDER_DEVELOPER_GUIDE.md)
- [Messy provider playbook](docs/10_MESSY_PROVIDER_PLAYBOOK.md)
- [Playback Gateway](docs/11_PLAYBACK_GATEWAY.md)
- [Legal reference sources](docs/12_LEGAL_REFERENCE_SOURCES.md)
- [OpenAPI mapping](spec/openapi.yaml)
- [JSON-RPC mapping](spec/mpp-jsonrpc.md)
- [Experimental capability contracts](spec/extensions/v0.1/README.md)
- [Capability Broker](../docs/developers/16_CAPABILITY_BROKER.md)
- [Build an enrichment plugin](../docs/tutorials/BUILD_AN_ENRICHMENT_PLUGIN.md)
- [Plugin Directory](../docs/PLUGIN_DIRECTORY.md)
- [Registry governance](../docs/developers/17_REGISTRY_GOVERNANCE.md)
- Registry review records: `registry/reviews/`

## Source neutrality

The SDK does not ship DRM/access-control circumvention, CAPTCHA bypass,
anti-bot evasion, private credentials, or connectors intended to obtain media
without authorization.

## License

MIT for SDK code and documentation unless a file states otherwise.

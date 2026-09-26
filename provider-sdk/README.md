# Melodex Provider SDK

A source-neutral, cross-platform provider protocol and developer SDK for **Melodex**.

> Melodex owns playback, Flow, taste, queueing and LLM control. Providers only supply catalog and playback access.

The Provider SDK is designed so Melodex can connect to user-authorized music libraries and services without baking any one source into the player.

## Why this exists

Melodex should be simple for ordinary listeners and extensible for developers. The provider layer gives both groups what they need:

- **macOS / Windows / Linux:** built-in sources, local provider processes, or a remote Provider Bridge.
- **Android / iOS:** built-in sources and Provider Bridge; no downloaded executable plugin code in store builds.
- **LLMs:** interact with normalized Melodex actions and catalog objects, never provider credentials or implementation details.
- **Provider authors:** implement one stable protocol rather than depending on Melodex's internal GUI or database.

## Repository status

**Protocol/SDK preview — v0.1.0.** The protocol is intentionally small and may change before a 1.0 compatibility guarantee.

Included today:

- MPP HTTP/OpenAPI specification;
- provider manifest and catalog JSON Schemas;
- Python reference models;
- `melodex-provider` CLI for `init`, `validate`, and `pack`;
- a fictional demo provider using only reserved `.invalid` media URLs;
- architecture, UX, mobile/desktop, security, LLM, and migration documentation;
- GitHub Actions CI and contribution/security templates.

## Quick start

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\\Scripts\\activate
python -m pip install -e '.[dev]'
```

Create a provider skeleton:

```bash
melodex-provider init my-provider
```

Validate its manifest:

```bash
melodex-provider validate my-provider
```

Package it as a desktop provider bundle:

```bash
melodex-provider pack my-provider
```

The result is a `.mdxprovider` ZIP-compatible bundle.

## Demo provider

The demo is intentionally fictional and does not depend on any external music service.

```bash
python examples/demo_provider/server.py
```

Then:

```bash
curl http://127.0.0.1:8877/v1/health
curl -H 'Authorization: Bearer demo-token' http://127.0.0.1:8877/v1/provider
```

## Architecture in one picture

```text
                         Melodex Core
                playback • Flow • taste • LLM
                              │
                       Provider Manager
                    ┌─────────┴─────────┐
                    │                   │
          desktop provider        Provider Bridge
             subprocess            HTTPS + token
                    │                   │
          user-authorized source   provider host/server
```

Providers do **not** control the Melodex GUI, Flow engine, taste database, Moments/Vibes, or LLM action executor.

## Start reading

- [Architecture](docs/01_ARCHITECTURE.md)
- [User experience](docs/02_USER_EXPERIENCE.md)
- [Platform matrix](docs/03_PLATFORM_MATRIX.md)
- [Provider developer guide](docs/04_PROVIDER_DEVELOPER_GUIDE.md)
- [Security and trust](docs/05_SECURITY_AND_TRUST.md)
- [LLM integration](docs/06_LLM_INTEGRATION.md)
- [Melodex migration plan](docs/07_MELODEX_V15_MIGRATION.md)
- [Release and repository policy](docs/08_RELEASE_AND_REPOSITORY_POLICY.md)
- [Protocol compatibility](docs/09_PROTOCOL_COMPATIBILITY.md)
- [GitHub upload guide](GITHUB_UPLOAD.md)

Protocol files:

- [`spec/openapi.yaml`](spec/openapi.yaml)
- [`spec/provider_manifest.schema.json`](spec/provider_manifest.schema.json)
- [`spec/catalog_item.schema.json`](spec/catalog_item.schema.json)
- [`spec/track.schema.json`](spec/track.schema.json)
- [`spec/mpp-jsonrpc.md`](spec/mpp-jsonrpc.md)

## Source neutrality

This public SDK is for generic media-source integration. It does not ship source-specific bypass logic, DRM/access-control circumvention helpers, or connectors intended to obtain media without authorization.

Provider authors are responsible for having permission to access and expose media from the source they integrate. See [Release and repository policy](docs/08_RELEASE_AND_REPOSITORY_POLICY.md).

## Security

Third-party providers should be treated as untrusted network clients, not imported into the Melodex GUI process. See [SECURITY.md](SECURITY.md) and [Security and trust](docs/05_SECURITY_AND_TRUST.md).

## License

The SDK, specifications, examples, and documentation in this repository are released under the [MIT License](LICENSE), unless a file states otherwise.

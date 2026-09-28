# Contributing to Melodex

Thanks for helping build Melodex.

The project welcomes small focused contributions. You do not need to understand the whole player before contributing.

## Choose your contribution path

### Player / UI
Work mainly in `desktop/` or `android/`.

### Music provider
Use the public Provider SDK in `provider-sdk/`. Do not add source-specific web/API logic directly to Melodex Core unless it is a deliberate first-party integration.

Start with `docs/tutorials/BUILD_A_PROVIDER.md`.

### Metadata / artwork / identity extension
Use the experimental capability contracts.

Start with `docs/tutorials/BUILD_AN_ENRICHMENT_PLUGIN.md`.

### API / automation
Use REST/OpenAPI, MCP or OpenAI function tools.

Start with `docs/DEVELOPERS.md`.

### Documentation / testing
Documentation, fixtures and testing improvements are first-class contributions.

## Before coding

For a substantial architectural change, open an issue first. Small fixes, docs and focused tests can usually go directly to a PR.

## Tests

Desktop:

```bash
cd desktop
PYTHONPATH=. pytest -q tests
```

Provider SDK:

```bash
cd provider-sdk
pytest -q tests
```

Repository checks:

```bash
python scripts/release_check.py
```

## Provider/plugin contributions

Public extensions should include a README, licence, tests/fixtures and `SOURCE_POLICY.md`.

The source policy should document the upstream API/access method, authentication, rate limit, data/media rights, caching/offline restrictions, commercial restrictions and attribution requirements.

See `docs/developers/11_SOURCE_AND_RIGHTS_POLICY.md`.

## Security

Never commit API keys, passwords, cookies, Bridge tokens, MCP tokens, private signed media URLs or copyrighted media used only as a test fixture.

## Pull requests

Keep PRs focused. Explain:

1. what changed;
2. why it is useful;
3. how it was tested;
4. documentation impact;
5. source/rights implications, when relevant.

## Design principles

- Core stays source-neutral.
- Providers own source-specific logic.
- Capability plugins should do one job well.
- AI integrations use high-level Melodex actions.
- Playback permission does not automatically imply download permission.
- External metadata/artwork should retain provenance where practical.

See [Community](docs/COMMUNITY.md) for non-code contribution paths.

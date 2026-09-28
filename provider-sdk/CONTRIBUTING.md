# Contributing

Thanks for helping improve the Melodex Provider SDK.

For a first provider/extension, the shortest route is the repository-level [5-minute developer quickstart](../docs/DEVELOPER_QUICKSTART.md).

## Scope

This repository is for the source-neutral provider protocol, SDK, schemas, examples, and documentation. Provider-specific integrations should normally live in their own repositories.

Please do not submit:

- DRM/access-control circumvention code;
- credentials, cookies, API secrets, or signed playback URLs;
- source-specific bypass logic intended to obtain media without authorization;
- connectors whose legal/authorization basis cannot be explained by the provider author.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\\Scripts\\activate
python -m pip install -e '.[dev]'
pytest
ruff check .
python ../scripts/docs_check.py
```

## Pull requests

Keep protocol changes small and explicit. A protocol PR should usually include:

1. the specification/schema change;
2. corresponding SDK/model changes;
3. tests;
4. documentation;
5. a note in `CHANGELOG.md`;
6. compatibility impact (backward-compatible, additive, or breaking).

## Provider examples

Examples must be safe to publish. Prefer fictional catalogs, local files created for testing, public-domain media, or services with clearly documented developer authorization.

## Commit style

No strict convention is required, but concise imperative subjects are preferred, for example:

- `Add album catalog schema`
- `Validate provider network hosts`
- `Document iOS bridge model`


## Compatibility / truth labels

The SDK is still 0.x and MPP 1.0 remains a preview compatibility target.

Protocol/docs PRs should explicitly say whether a change is:

- implemented;
- preview;
- experimental;
- planned;
- historical.

See [Status, stability and trust](../docs/developers/00_STATUS_AND_STABILITY.md).

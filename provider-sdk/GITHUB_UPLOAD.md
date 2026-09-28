# Provider SDK Repository Location

The Melodex Provider SDK currently lives inside the main Melodex repository:

```text
https://github.com/Cliff-Lee/melodex
└── provider-sdk/
```

The older idea of uploading this directory as a separate `melodex-provider-sdk` repository is not the current publishing workflow.

## Contributing to the SDK

Work in the main repository and open a pull request.

From `provider-sdk/`:

```bash
python -m pip install -e '.[dev]'
pytest -q tests
melodex-registry validate registry/registry.json
melodex-registry verify-packages registry/registry.json --packages registry/packages
```

From the repository root also run:

```bash
python scripts/docs_check.py
python scripts/ecosystem_check.py
python scripts/version_check.py
python scripts/release_check.py
```

See:

- [Provider SDK README](README.md)
- [Contributing](CONTRIBUTING.md)
- [Release checklist](RELEASE_CHECKLIST.md)
- [Repository-level contributing guide](../CONTRIBUTING.md)

## If the SDK is split into a standalone repository later

That would be an explicit project decision with updated URLs, CI, release/version policy and documentation.

Do not treat historical standalone-repository examples as current instructions.

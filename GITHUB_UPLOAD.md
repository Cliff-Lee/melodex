# Repository and Release Workflow

Melodex is already public at:

`https://github.com/Cliff-Lee/melodex`

This file is retained as a short publishing pointer. The old bootstrap instructions for creating the repository and tagging the first release are no longer the normal workflow.

## Contributing changes

Normal development should use a branch and pull request against `main`.

Before proposing a substantial change, run the checks relevant to your work. The full repository checks are:

```bash
python scripts/docs_check.py
python scripts/ecosystem_check.py
python scripts/version_check.py
python scripts/release_check.py

PYTHONPATH=desktop pytest -q desktop/tests
pytest -q provider-sdk/tests
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Publishing a tagged release

Do not copy an old hard-coded tag such as `v0.1.0`.

Follow:

- [Releasing Melodex](docs/RELEASING.md)
- [Releases, `main`, and version numbers](docs/RELEASES_AND_MAIN.md)

The release workflows verify that the Git tag matches the application version before producing/attaching supported platform artifacts.

## Historical bootstrap helper

`scripts/publish_github.sh` was useful while creating the public repository.

It is **not** the normal update/release mechanism for the existing repository.

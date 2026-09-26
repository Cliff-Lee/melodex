# Contributing

Contributions are welcome.

For player/UI work, use `desktop/` or `android/`.
For music-source integrations, prefer the public Provider SDK rather than adding source-specific scraping logic to Melodex Core.

Before opening a pull request:

```bash
cd desktop
PYTHONPATH=. pytest -q tests
cd ../provider-sdk
pytest -q tests
cd ..
python scripts/release_check.py
```

Keep public Melodex source-neutral and do not commit credentials or copyrighted media.

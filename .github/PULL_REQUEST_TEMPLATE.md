## What changed?

Briefly describe the change and why it is useful.

## Area

- [ ] Desktop app
- [ ] Android app
- [ ] Provider SDK / playback provider
- [ ] Capability extension
- [ ] REST / OpenAPI
- [ ] MCP / OpenAI integration
- [ ] Plugin registry / ecosystem
- [ ] Documentation
- [ ] Build / release tooling

## Testing

Describe what you ran or checked.

For repository-wide changes, useful checks include:

```bash
python scripts/docs_check.py
python scripts/ecosystem_check.py
python scripts/api_docs_check.py
python scripts/release_check.py
```

## Source / rights impact

For provider or external-data changes:

- Upstream source:
- API/access method:
- Caching/offline implications:
- Attribution/licence implications:

Use `N/A` when this does not apply.

## Checks

- [ ] I tested the change locally where practical.
- [ ] I did not commit credentials, private tokens or copyrighted media.
- [ ] Provider-specific integration logic remains outside Melodex Core.
- [ ] Playback permission is not assumed to mean download permission.
- [ ] Relevant tests and documentation have been updated.
- [ ] External metadata/artwork provenance is preserved where relevant.
- [ ] Registry package URL, SHA-256 and byte size match the published package where applicable.
- [ ] Registry permissions and compatibility metadata are accurate where applicable.
- [ ] Documentation distinguishes current main, packaged-release availability, experimental/preview status, and planned behavior where relevant.
- [ ] Security wording distinguishes declared permissions / process isolation from OS-enforced sandboxing.
- [ ] App/release version metadata and RELEASE_STATUS.md were considered if this changes shipped behavior or release tooling.

## Screenshots / notes

Add screenshots, logs, API payloads or implementation notes when they help reviewers.

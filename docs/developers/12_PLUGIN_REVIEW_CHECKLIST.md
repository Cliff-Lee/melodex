# Plugin Review Checklist

Use this before listing an extension in the Melodex registry.

## Identity

- [ ] Stable plugin ID
- [ ] Version present
- [ ] Publisher/contact information present
- [ ] Source repository available

## Protocol

- [ ] Declared capabilities are implemented
- [ ] Unsupported methods fail cleanly
- [ ] stdout contains protocol JSON only
- [ ] stderr is used for logs
- [ ] Stable provider IDs are not temporary media URLs

## Security

- [ ] No secrets committed
- [ ] Credentials stay out of metadata/provenance
- [ ] Network permissions are minimal
- [ ] Local-file/browser-auth permissions are justified
- [ ] Offline/download permission is justified

## Network behavior

- [ ] Meaningful User-Agent
- [ ] Timeouts
- [ ] Published rate limits respected
- [ ] Bounded retries/backoff
- [ ] Upstream outages handled without crashing Melodex

## Source/rights

- [ ] `SOURCE_POLICY.md` included
- [ ] API terms reviewed
- [ ] Media/data rights documented
- [ ] Attribution preserved where required
- [ ] Per-item licences preserved where required
- [ ] Caching/offline/commercial restrictions documented

## Testing

- [ ] Offline fixtures
- [ ] Normalization tests
- [ ] Schema/protocol tests
- [ ] Live tests isolated and optional

# Plugin Registry Governance

The Melodex registry is an index of independently developed extensions.

It should not become a central repository of opaque integration code.

## Decentralized model

Normal community flow:

```text
author repository
    ↓
source + tests + docs
    ↓
release .mdxprovider / .mdxplugin
    ↓
registry entry points to that release
    ↓
Melodex Plugin Directory
```

Authors retain control of their repositories and releases.

## Registry PR requirements

A new community entry should normally include:

```text
stable reverse-domain ID
publisher
version
kind
capabilities
licence
source repository
HTTPS package URL
SHA-256
package byte size
compatibility
declared permissions
SOURCE_POLICY link
review record link
```

The source repository should contain enough information for reviewers/users to understand what the extension does.

## Validation

From `provider-sdk/`:

```bash
melodex-registry validate registry/registry.json
```

For packages stored in the Melodex repository:

```bash
melodex-registry verify-packages \
  registry/registry.json \
  --packages registry/packages
```

Validate review history too:

```bash
melodex-registry validate-reviews \
  registry/registry.json \
  --reviews registry/reviews
```

CI checks the canonical registry/package set and its review records.

## Review records

Every canonical registry entry has an append-only JSON record under:

```text
provider-sdk/registry/reviews/<plugin-id>.json
```

The registry entry links to that file and records the date of the latest event.

Each event identifies:

- review timestamp and reviewer;
- decision;
- plugin version;
- package SHA-256 when an installable package exists;
- checks performed;
- a short summary;
- explicit limitations.

The latest event must match the exact version and package hash currently published by the registry.

Decision vocabulary maps to registry status:

```text
example      → example-baseline
community    → community-intake
reviewed     → reviewed
deprecated   → deprecated
blocked      → blocked
```

A `community-intake` event records that the entry passed the registry intake needed for listing. It does **not** mean the plugin has the stronger `reviewed` status.

Review files are append-only in normal operation: a new release or status decision appends a new event rather than rewriting an older event.

A contributor may propose the review-record change in the same PR, but the final reviewer identity/summary should reflect the actual registry review outcome before merge. Contributors should not self-promote an entry to `reviewed`.

## Review questions

Technical review should ask:

1. Does the package match its declared SHA-256?
2. Is the plugin ID stable and unique?
3. Are capabilities narrow and accurate?
4. Are permissions honest and minimal?
5. Are secrets absent?
6. Are timeouts/outages handled?
7. Are provider/extension protocol outputs clean?
8. Does it preserve relevant provenance?
9. Is the source/API access method documented?
10. Does download/offline behavior match the upstream rights model?

## Status transitions

Typical lifecycle:

```text
community
   ↓
reviewed
   ↓
deprecated
```

`example` is reserved for project reference examples.

`blocked` is for entries that should no longer be offered to users, for example because of a serious security, integrity or policy problem.

Status changes should be made through a visible registry PR with a reason and a matching appended review event.

## Updating a release

Do not silently replace bytes behind the same registry digest.

For a new release:

1. publish/build the new package;
2. update `version`;
3. update `package_url` when appropriate;
4. calculate the new SHA-256 and size;
5. update compatibility/permissions if needed;
6. append a review event for the new version/hash and update `review.last_reviewed_at`;
7. run registry and review-history validation;
8. open a PR.

## Rights review

Registry inclusion does not transfer rights in media, metadata, artwork or lyrics.

The extension's `SOURCE_POLICY.md` should describe:

- official/documented access method;
- authentication;
- rate limits;
- data/media licence;
- per-item rights where relevant;
- caching;
- offline/download rules;
- commercial restrictions;
- attribution.

## Security model today

Registry SHA-256 protects package integrity relative to the registry.

Current provider/extension process separation improves fault isolation but is not a full sandbox.

Publisher signatures, stronger sandboxing and richer permission enforcement remain roadmap work.

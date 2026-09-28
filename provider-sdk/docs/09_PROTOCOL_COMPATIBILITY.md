# 9. Protocol compatibility and versioning

The repository is currently an SDK/protocol **preview**. SDK package version `0.x` does not promise compatibility between every minor release, and the current MPP `protocol_version: "1.0"` identifier should not yet be read as a frozen final 1.0 contract.

## Manifest versus protocol version

These are intentionally separate:

- `schema_version` — shape/version of `manifest.json`;
- `protocol_version` — MPP wire contract implemented by the provider.

A provider may update its own package `version` without changing either of these.

## Planned 1.x policy

After MPP 1.0 is declared stable:

- additive optional response fields are backward-compatible;
- new optional capabilities/methods are backward-compatible when capability-negotiated;
- removing or changing required fields requires a new protocol major version;
- unknown response fields must be ignored by clients unless a schema explicitly says otherwise;
- providers must not advertise capabilities they do not implement;
- Melodex should fail closed for unknown permissions or playback policies.

## Capability negotiation

Provider metadata returns a `capabilities` array. Melodex must check capabilities before exposing related UI or calling optional methods. A missing capability is not an error; it means the feature is unavailable for that provider.

## Compatibility testing

Current tooling includes `validate` plus `doctor` smoke tests for local provider packages.

Before a stable 1.0 commitment, the project still needs a fuller conformance runner that can validate schemas, error handling, pagination, authentication requirements, playback policy, timeouts and compatibility fixtures across releases.

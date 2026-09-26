# 9. Protocol compatibility and versioning

The repository is currently an SDK/protocol **preview**. Package version `0.x` does not promise wire compatibility between minor releases.

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

Before 1.0, the project should add a conformance runner that can point at either:

- a local JSON-RPC provider process; or
- an HTTP Provider Bridge endpoint.

The runner should validate schemas, error handling, pagination, authentication requirements, playback policy, and timeout behavior.

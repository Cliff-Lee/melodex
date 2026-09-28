# Testing Extensions

A healthy ecosystem needs fast offline tests and optional live smoke tests.

## Test layers

### 1. Normalization tests

Given a saved upstream fixture, verify the normalized Melodex result.

### 2. Contract/schema tests

Validate request/response payloads against Melodex schemas.

### 3. Protocol tests

Start the provider/extension process and send JSON-RPC requests.

### 4. Integration tests

Install the resulting package into a temporary Melodex data directory and call it through the Provider Manager or Capability Broker.

### 5. Live smoke tests

Optional tests against the real upstream service.

Keep these separate from unit tests because networks, rate limits and upstream outages are not unit-test failures.

## Provider checks

```bash
melodex-provider validate .
melodex-provider doctor .
melodex-provider pack .
```

## Capability-extension checks

```bash
melodex-extension validate .
melodex-extension doctor .
melodex-extension pack .
```

## Fixture mode

Reference extensions should provide saved upstream fixtures wherever practical.

A good CI test should be able to prove:

```text
input fixture
→ extension normalization
→ contract-shaped result
```

without internet access.

## Registry-review minimum

A community extension should normally demonstrate:

```text
descriptor/schema valid
no secrets committed
offline fixture tests pass
protocol stdout clean
permissions documented
source policy documented
timeouts handled
not-found handled
provenance preserved
```

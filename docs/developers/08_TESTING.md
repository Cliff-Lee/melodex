# Testing Extensions

A healthy ecosystem needs fast offline tests and optional live smoke tests.

## Test layers

### 1. Normalization tests

Given a saved upstream fixture, verify the normalized Melodex result.

### 2. Contract/schema tests

Validate request/response payloads against Melodex schemas.

### 3. Protocol tests

Start the provider/extension process and send JSON-RPC requests.

### 4. Live smoke tests

Optional tests against the real upstream service.

Keep these separate from unit tests because networks, rate limits and upstream outages are not unit-test failures.

## Provider SDK checks

```bash
melodex-provider validate .
melodex-provider doctor .
melodex-provider pack .
```

## Registry-review minimum

A community extension should normally demonstrate:

```text
manifest/schema valid
no secrets committed
offline fixture tests pass
protocol stdout clean
permissions documented
source policy documented
timeouts handled
not-found handled
```

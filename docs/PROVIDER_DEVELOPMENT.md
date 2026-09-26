# Writing a Melodex provider

The complete SDK is in [`../provider-sdk`](../provider-sdk).

## Fast path

```bash
cd provider-sdk
python -m venv .venv
source .venv/bin/activate
pip install -e .
melodex-provider init my-provider
melodex-provider validate my-provider
melodex-provider pack my-provider
```

The resulting `.mdxprovider` can be installed into desktop Melodex.

## Required semantic operations

A playback provider normally implements:

- `provider.info`
- `provider.health`
- `catalog.search`
- `catalog.get_track`
- `playback.resolve`

Desktop providers use newline-delimited JSON-RPC over stdin/stdout. Remote/Bridge providers use the HTTP/OpenAPI mapping.

Read:

- `provider-sdk/docs/01_ARCHITECTURE.md`
- `provider-sdk/docs/04_PROVIDER_DEVELOPER_GUIDE.md`
- `provider-sdk/docs/05_SECURITY_AND_TRUST.md`
- `provider-sdk/spec/mpp-jsonrpc.md`
- `provider-sdk/spec/openapi.yaml`

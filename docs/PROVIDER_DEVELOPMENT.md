# Writing a Melodex Provider

Want the shortest route? Start with the **[5-minute developer quickstart](DEVELOPER_QUICKSTART.md)**.

The complete SDK is in [`../provider-sdk`](../provider-sdk).

## Fast path

```bash
cd provider-sdk
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
melodex-provider init my-provider
melodex-provider validate my-provider
melodex-provider doctor my-provider
melodex-provider pack my-provider
```

## Clean and messy providers are both supported

A clean API provider may map JSON directly into Melodex objects. A messy provider
may search HTML/XML, follow detail pages, maintain a session, resolve redirects
and obtain a temporary media URL. That complexity stays inside the provider.

Start with:

- `provider-sdk/docs/04_PROVIDER_DEVELOPER_GUIDE.md`
- `provider-sdk/docs/10_MESSY_PROVIDER_PLAYBOOK.md`
- `provider-sdk/docs/11_PLAYBACK_GATEWAY.md`
- `provider-sdk/docs/12_LEGAL_REFERENCE_SOURCES.md`
- `provider-sdk/spec/mpp-jsonrpc.md`
- `provider-sdk/spec/openapi.yaml`

The public SDK remains source-neutral and does not include access-control bypass,
DRM circumvention, CAPTCHA solving or credentials.


## Before depending on a contract

Read [Status, stability and trust](developers/00_STATUS_AND_STABILITY.md). MPP is implemented and usable, but the SDK is still 0.x and the current `protocol_version: "1.0"` remains a preview compatibility target.

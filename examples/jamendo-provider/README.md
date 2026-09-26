# Jamendo MPP reference provider

This example demonstrates a real online Melodex Provider Protocol connector using the public Jamendo API.

It requires **your own** Jamendo developer client ID:

```bash
export JAMENDO_CLIENT_ID=your_client_id
python provider.py
```

Package it with the Provider SDK after reviewing Jamendo's current API terms and the licences of content returned by the API.

The example declares no offline-download capability and retains attribution, source-page and licence metadata.

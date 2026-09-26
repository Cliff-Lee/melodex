# Demo provider

This is a deliberately fictional MPP HTTP provider. It exists only to exercise the protocol.

- Catalog entries are invented.
- Media URLs use the reserved `.invalid` domain and cannot fetch real audio.
- The development bearer token is `demo-token`.

Run:

```bash
python server.py
```

Health check:

```bash
curl http://127.0.0.1:8877/v1/health
```

Provider metadata:

```bash
curl -H 'Authorization: Bearer demo-token' http://127.0.0.1:8877/v1/provider
```

# MPP local-process mapping (JSON-RPC over stdio)

Desktop `.mdxprovider` bundles may run as child processes. The semantic operations are the same as the HTTP/OpenAPI mapping, but messages are carried as newline-delimited JSON-RPC 2.0 on standard input/output.

## Transport rules

- stdin: requests from Melodex to the provider;
- stdout: protocol responses only;
- stderr: human-readable provider logs;
- UTF-8, one complete JSON object per line;
- providers must not write banners or debug text to stdout;
- Melodex may terminate a provider after a request timeout or malformed protocol output.

## Method mapping

| MPP semantic method | JSON-RPC method | HTTP equivalent |
|---|---|---|
| provider.info | `provider.info` | `GET /v1/provider` |
| provider.health | `provider.health` | `GET /v1/health` |
| catalog.search | `catalog.search` | `POST /v1/search` |
| catalog.get_track | `catalog.get_track` | `GET /v1/tracks/{id}` |
| catalog.get_album | `catalog.get_album` | `GET /v1/albums/{id}` |
| catalog.get_artist | `catalog.get_artist` | `GET /v1/artists/{id}` |
| playback.resolve | `playback.resolve` | `POST /v1/playback/resolve` |

## Example

Request:

```json
{"jsonrpc":"2.0","id":1,"method":"catalog.search","params":{"query":"example","types":["track"],"limit":25,"cursor":null}}
```

Response:

```json
{"jsonrpc":"2.0","id":1,"result":{"items":[],"next_cursor":null}}
```

Error:

```json
{"jsonrpc":"2.0","id":1,"error":{"code":-32001,"message":"Sign-in required","data":{"mpp_code":"AUTH_REQUIRED","retryable":false}}}
```

The JSON-RPC transport itself does not grant additional permissions. The provider manifest and Melodex trust model remain authoritative.

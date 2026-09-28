# Tutorial — Control Melodex with REST

Use Melodex's local control API when you are building your own controller, automation or app.

## 1. Start Melodex

The desktop application starts a loopback bridge and writes its active host, port and bearer token into Melodex application data.

Treat the token like a password.

## 2. Check health

```bash
curl http://127.0.0.1:<port>/health
```

## 3. List providers

```bash
curl \
  -H "Authorization: Bearer $MELODEX_TOKEN" \
  "$MELODEX_URL/v1/providers"
```

## 4. Search

```bash
curl -G \
  -H "Authorization: Bearer $MELODEX_TOKEN" \
  --data-urlencode "q=Massive Attack" \
  "$MELODEX_URL/v1/search"
```

## 5. Resolve without playing

```bash
curl -G \
  -H "Authorization: Bearer $MELODEX_TOKEN" \
  --data-urlencode "artist=Massive Attack" \
  --data-urlencode "title=Teardrop" \
  "$MELODEX_URL/v1/resolve"
```

## 6. Play

```bash
curl \
  -H "Authorization: Bearer $MELODEX_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"artist":"Massive Attack","title":"Teardrop"}' \
  "$MELODEX_URL/v1/play"
```

## 7. Queue tracks

```json
{
  "tracks": [
    {"artist": "Massive Attack", "title": "Teardrop"},
    {"artist": "Portishead", "title": "Roads"}
  ],
  "mode": "replace",
  "autoplay": true
}
```

Send that to `POST /v1/queue`.

## 8. Control playback

Example:

```json
{
  "action": "set_volume",
  "args": {"value": 0.65}
}
```

Send to `POST /v1/control`.

## Security

Keep the bridge on loopback unless LAN access is intentional. Use a trusted VPN/TLS proxy for access across untrusted networks.

See [API platform](../api/README.md).

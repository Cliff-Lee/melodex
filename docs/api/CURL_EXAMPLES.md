# cURL Examples

Assume:

```bash
export MELODEX_URL=http://127.0.0.1:49152
export MELODEX_TOKEN='replace-me'
```

## Health

```bash
curl "$MELODEX_URL/health"
```

## OpenAPI

```bash
curl "$MELODEX_URL/openapi.json"
```

## Providers

```bash
curl -H "Authorization: Bearer $MELODEX_TOKEN" \
  "$MELODEX_URL/v1/providers"
```

## Search

```bash
curl -G \
  -H "Authorization: Bearer $MELODEX_TOKEN" \
  --data-urlencode "q=Massive Attack" \
  --data-urlencode "provider=all" \
  "$MELODEX_URL/v1/search"
```

## Play

```bash
curl \
  -H "Authorization: Bearer $MELODEX_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"artist":"Massive Attack","title":"Teardrop"}' \
  "$MELODEX_URL/v1/play"
```

## OpenAI function definitions

```bash
curl -H "Authorization: Bearer $MELODEX_TOKEN" \
  "$MELODEX_URL/v1/openai/tools"
```

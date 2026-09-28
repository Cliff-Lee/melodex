# Tutorial — Build a Melodex Provider

This is the shortest path from "I know a music source" to an installable `.mdxprovider`.

## 1. Install the SDK

```bash
cd provider-sdk
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e '.[dev]'
```

## 2. Generate a provider

```bash
melodex-provider init hello-provider \
  --id org.example.hello \
  --name "Hello Provider"
```

You get:

```text
hello-provider/
├── manifest.json
├── provider.py
├── README.md
├── LICENSE
└── vendor/
```

## 3. Implement the current MPP methods

A typical playback provider implements:

```text
provider.info
provider.health
catalog.search
catalog.get_track
playback.resolve
```

Keep discovery and playback separate:

```text
catalog.search
      ↓
stable provider_track_id
      ↓
playback.resolve
      ↓
current URL / headers / cookies / expiry
```

Do not use a temporary CDN URL as permanent track identity.

## 4. Normalize source data

Example:

```json
{
  "type": "track",
  "provider_id": "org.example.hello",
  "provider_track_id": "12345",
  "artist": "Example Artist",
  "title": "Example Track",
  "album": "Example Album"
}
```

## 5. Resolve playback

Example:

```json
{
  "kind": "http",
  "url": "https://cdn.example.org/audio/12345.mp3",
  "headers": {},
  "cookies": {},
  "seekable": true,
  "cache_policy": "session"
}
```

## 6. Validate and test

```bash
melodex-provider validate hello-provider
melodex-provider doctor hello-provider
```

## 7. Package

```bash
melodex-provider pack hello-provider
```

Result:

```text
hello-provider.mdxprovider
```

## 8. Before publishing

Add a `SOURCE_POLICY.md` explaining:

- API/access method;
- authentication;
- rate limits;
- data/media rights;
- attribution;
- caching;
- offline/download rules;
- commercial restrictions.

Then read [Source and rights policy](../developers/11_SOURCE_AND_RIGHTS_POLICY.md).

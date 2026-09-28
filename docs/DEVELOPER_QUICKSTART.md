# Build Something for Melodex in 5 Minutes

You do **not** need to understand the Melodex player, Flow, Qt, the resolver, or the AI stack to build an extension.

Start by choosing one job:

| I want to… | Build |
| --- | --- |
| Search/play music from a source | `.mdxprovider` |
| Add identity, metadata, artwork or lyrics | `.mdxplugin` |
| Control a running Melodex app | REST / OpenAPI / MCP / OpenAI tools |

This page is the shortest route to a working extension. The deeper documentation is linked at the end.

## One-time setup

From a clone of Melodex:

```bash
cd provider-sdk
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Windows PowerShell:

```powershell
cd provider-sdk
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e '.[dev]'
```

You now have:

```text
melodex-provider
melodex-extension
melodex-registry
```

---

# Route A — music source / playback provider

Create it:

```bash
melodex-provider init hello-provider \
  --id org.example.hello \
  --name "Hello Provider"
```

Generated:

```text
hello-provider/
├── manifest.json
├── provider.py
├── README.md
├── SOURCE_POLICY.md
├── LICENSE
└── vendor/
```

Immediately check it:

```bash
melodex-provider validate hello-provider
melodex-provider doctor hello-provider
```

The generated provider already speaks MPP and returns a demo catalog/playback shape. Replace the demo logic in `provider.py` with your source.

The two ideas to keep separate are:

```text
catalog.search
      ↓
stable provider_track_id
      ↓
playback.resolve
      ↓
current playable resource
```

Do not use a temporary CDN URL as track identity.

If your provider needs a user-entered token or setting, declare it in `manifest.json` rather than embedding it:

```json
"configuration": [
  {"key": "api_token", "label": "API token", "type": "secret", "required": true}
]
```

Read [Build a provider](tutorials/BUILD_A_PROVIDER.md) for the runtime access pattern.

Package it:

```bash
melodex-provider pack hello-provider
```

Result:

```text
hello-provider.mdxprovider
```

---

# Route B — metadata / artwork / identity / lyrics

Create one narrow capability:

```bash
melodex-extension init hello-artwork \
  --id org.example.artwork \
  --name "Hello Artwork" \
  --capability artwork
```

Other current v0.1 capability choices are:

```text
identity
metadata
artwork
lyrics
```

Check it:

```bash
melodex-extension validate hello-artwork
melodex-extension doctor hello-artwork
```

Edit `plugin.py` so the capability returns real sourced data.

Keep provenance with externally supplied data:

```json
{
  "url": "https://example.org/image.jpg",
  "role": "portrait",
  "score": 0.9,
  "provenance": {
    "source_extension_id": "org.example.artwork",
    "source_url": "https://example.org/item/123",
    "retrieved_at": "2026-09-28T00:00:00Z",
    "license": "CC BY 4.0",
    "attribution": "Example Photographer"
  }
}
```

Package it:

```bash
melodex-extension pack hello-artwork
```

Result:

```text
hello-artwork.mdxplugin
```

---

# Install your local build

In desktop Melodex:

```text
Sources
→ Show power tools
→ Install .mdxprovider…
```

or:

```text
Sources
→ Show power tools
→ Install .mdxplugin…
```

A manual install records a local package SHA-256, but it is **not** described as registry-verified.

For public/community releases, use the Plugin Directory/registry path instead.

---

# Publish it to the Plugin Directory

Normal community flow:

```text
your repository
    ↓
tests + documentation + SOURCE_POLICY.md
    ↓
.mdxprovider / .mdxplugin release
    ↓
registry entry
    ↓
Sources → Explore plugins…
```

Read [Publish a community plugin](tutorials/ADD_PLUGIN_TO_REGISTRY.md).

Melodex requires installable registry entries to publish an HTTPS package URL, SHA-256, and byte size.

---

# What should I read next?

| Need | Read |
| --- | --- |
| Full provider walkthrough | [Build a provider](tutorials/BUILD_A_PROVIDER.md) |
| Full enrichment walkthrough | [Build an enrichment plugin](tutorials/BUILD_AN_ENRICHMENT_PLUGIN.md) |
| What is stable vs experimental? | [Status and stability](developers/00_STATUS_AND_STABILITY.md) |
| How the pieces fit together | [Ecosystem architecture](developers/01_ECOSYSTEM_ARCHITECTURE.md) |
| Provider protocol details | [Provider SDK](../provider-sdk/README.md) |
| Composition/provenance | [Composition and provenance](developers/06_COMPOSITION_AND_PROVENANCE.md) |
| Security reality | [Permissions and security](developers/07_PERMISSIONS_SECURITY.md) |
| Testing | [Testing extensions](developers/08_TESTING.md) |
| Registry publishing | [Registry governance](developers/17_REGISTRY_GOVERNANCE.md) |
| Example code | [Reference extensions](developers/13_EXAMPLE_PLUGINS.md) |

## One principle to remember

> **Build one useful thing.**

A playback provider does not need to become a metadata database. An artwork extension does not need to understand the queue. A controller does not need provider credentials.

That separation is the ecosystem.

# Melodex Documentation Map

This is the complete human-facing documentation map.

**Default scope:** current documentation describes the current public `main` branch unless a page explicitly says it is release-specific, historical, or a design target.

For the packaged-build gap, see [Release status](RELEASE_STATUS.md).

---

## Start here — users

- [Documentation home](README.md)
- [Start Here](START_HERE.md)
- [5-minute Visual Tour](VISUAL_TOUR.md)
- [Why Melodex?](WHY_MELODEX.md)
- [User Guide](USER_GUIDE.md)
- [FAQ](FAQ.md)
- [Troubleshooting](TROUBLESHOOTING.md)

## Installation and release availability

- [Installation chooser](INSTALL.md)
- [macOS installation](INSTALL_MACOS.md)
- [Windows installation](INSTALL_WINDOWS.md)
- [Android installation](INSTALL_ANDROID.md)
- [Release status — main vs packaged release](RELEASE_STATUS.md)

## User features / sources

- [Sources](SOURCES.md)
- [User Streams](USER_STREAMS.md)
- [Jamendo reference provider](JAMENDO_REFERENCE_PROVIDER.md)
- [Official/reference providers](OFFICIAL_PROVIDERS.md)
- [Playlist interchange](PLAYLIST_INTERCHANGE.md)
- [Universal Resolver](UNIVERSAL_RESOLVER.md)
- [Resolver Inspector](RESOLVER_INSPECTOR.md)
- [Rich Now Playing](RICH_NOW_PLAYING.md)

## Optional LLM / AI use

- [LLM Guide](LLM_GUIDE.md)
- [OpenWebUI](OPENWEBUI.md)
- [Ollama](OLLAMA.md)
- [MCP Control](MCP_CONTROL.md)

---

# Developer start pages

- [5-minute Developer Quickstart](DEVELOPER_QUICKSTART.md)
- [Develop with Melodex](DEVELOPERS.md)
- [Developer ecosystem index](developers/README.md)
- [Provider development](PROVIDER_DEVELOPMENT.md)
- [Provider installation](PROVIDER_INSTALLATION.md)
- [Provider SDK](../provider-sdk/README.md)

## Provider / plugin tutorials

- [Build a Provider](tutorials/BUILD_A_PROVIDER.md)
- [Build an Enrichment Plugin](tutorials/BUILD_AN_ENRICHMENT_PLUGIN.md)
- [Publish a Community Plugin](tutorials/ADD_PLUGIN_TO_REGISTRY.md)

## Plugin ecosystem reference

- [Status, stability and trust](developers/00_STATUS_AND_STABILITY.md)
- [Ecosystem architecture](developers/01_ECOSYSTEM_ARCHITECTURE.md)
- [Capability reference](developers/05_CAPABILITY_REFERENCE.md)
- [Composition and provenance](developers/06_COMPOSITION_AND_PROVENANCE.md)
- [Permissions and security](developers/07_PERMISSIONS_SECURITY.md)
- [Testing extensions](developers/08_TESTING.md)
- [Publishing and registry](developers/10_PUBLISHING_REGISTRY.md)
- [Source and rights policy](developers/11_SOURCE_AND_RIGHTS_POLICY.md)
- [Plugin review checklist](developers/12_PLUGIN_REVIEW_CHECKLIST.md)
- [Reference extensions](developers/13_EXAMPLE_PLUGINS.md)
- [Glossary](developers/15_GLOSSARY.md)
- [Capability Broker](developers/16_CAPABILITY_BROKER.md)
- [Registry governance](developers/17_REGISTRY_GOVERNANCE.md)
- [Plugin Directory](PLUGIN_DIRECTORY.md)

---

# API / automation / AI integration

## Tutorials

- [Control Melodex with REST](tutorials/CONTROL_MELODEX_WITH_REST.md)
- [Connect OpenWebUI with MCP](tutorials/CONNECT_OPENWEBUI_MCP.md)
- [Use OpenAI Function Calling](tutorials/USE_OPENAI_FUNCTIONS.md)

## API reference

- [API platform overview](api/README.md)
- [Local REST API](api/LOCAL_REST_API.md)
- [OpenAPI](api/OPENAPI.md)
- [cURL examples](api/CURL_EXAMPLES.md)
- [MCP and OpenWebUI](api/MCP_AND_OPENWEBUI.md)
- [OpenAI compatibility](api/OPENAI_COMPATIBILITY.md)
- [OpenAI function tools](api/OPENAI_FUNCTION_CALLING.md)
- [API security](api/SECURITY.md)
- [API architecture decision](api/ARCHITECTURE_DECISION.md)
- [API changelog](api/CHANGELOG.md)

---

# Privacy / security / community

- [Privacy](PRIVACY.md)
- [Security](../SECURITY.md)
- [Responsible Use](../RESPONSIBLE_USE.md)
- [Governance](../GOVERNANCE.md)
- [Code of Conduct](../CODE_OF_CONDUCT.md)
- [Contributing](../CONTRIBUTING.md)
- [Community](COMMUNITY.md)
- [Support](../SUPPORT.md)

---

# Build / release / project

- [Build from source](BUILD_FROM_SOURCE.md)
- [Releasing](RELEASING.md)
- [Release status](RELEASE_STATUS.md)
- [Project roadmap](../ROADMAP.md)
- [Third-party notices](../THIRD_PARTY_NOTICES.md)

---

# Current implementation notes

These pages document specific implemented subsystems. They are useful when working on that subsystem but are not the main user/developer entry point.

- [Artist visuals](ARTIST_VISUALS.md)
- [Progressive metadata loading](PROGRESSIVE_METADATA.md)
- [Wikimedia attribution](WIKIMEDIA_ATTRIBUTION.md)

---

# Historical / design / maintainer notes

These are retained for project history or maintenance. They should **not** override current status/architecture docs.

- [Parachord → Melodex feature map](PARACHORD_FEATURE_MAP.md) — historical comparison/roadmap notes
- [Parachord feature-map addendum](PARACHORD_FEATURE_MAP_ADDENDUM.md) — historical stage snapshot
- [GitHub social preview](SOCIAL_PREVIEW.md) — repository-maintainer asset note

For current truth, prefer:

- [Status, stability and trust](developers/00_STATUS_AND_STABILITY.md)
- [Ecosystem architecture](developers/01_ECOSYSTEM_ARCHITECTURE.md)
- [Release status](RELEASE_STATUS.md)

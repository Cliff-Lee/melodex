# Melodex Documentation

**Don't shuffle. Flow.**

This is the **friendly documentation map**: choose what you are trying to do and follow one route.

If you already know the exact document you need, use the [complete documentation index](ALL_DOCUMENTATION.md).

> Repository documentation follows current `main`; tagged binaries can lag behind it. See [Releases, `main`, and version numbers](RELEASES_AND_MAIN.md).

## I want to use Melodex

Start here:

1. [Start Here](START_HERE.md) — shortest first-use path.
2. [5-minute visual tour](VISUAL_TOUR.md) — see the main ideas/screens.
3. [User guide](USER_GUIDE.md) — learn the main player features.

Then use:

- [FAQ](FAQ.md) for common questions;
- [Troubleshooting](TROUBLESHOOTING.md) when something is not working;
- [Why Melodex?](WHY_MELODEX.md) for the design idea behind Flow and taste memory.

## I want to install Melodex

- [Installation chooser](INSTALL.md)
- [macOS](INSTALL_MACOS.md)
- [Windows](INSTALL_WINDOWS.md)
- [Android](INSTALL_ANDROID.md)

## I want optional AI control

- [LLM guide](LLM_GUIDE.md)
- [Ollama](OLLAMA.md)
- [OpenWebUI](OPENWEBUI.md)
- [MCP control](MCP_CONTROL.md)

Core playback, Flow and taste memory do not require an LLM.

## I want to add music sources

For users:

- [Music sources](SOURCES.md)
- [Installing providers/extensions](PROVIDER_INSTALLATION.md)
- [Plugin Directory](PLUGIN_DIRECTORY.md)

For developers:

- [5-minute developer quickstart](DEVELOPER_QUICKSTART.md)
- [Develop with Melodex](DEVELOPERS.md)

## I want to build something

Use the **[developer gateway](DEVELOPERS.md)**.

It routes you to the right interface:

```text
music source           → MPP / .mdxprovider
metadata/artwork/etc.  → .mdxplugin
external controller    → REST / OpenAPI
AI client              → MCP / OpenAI tools
public extension       → registry / Plugin Directory
```

For precise maturity/security status, use [Status, stability and trust](developers/00_STATUS_AND_STABILITY.md).

## I want to contribute to Melodex itself

- [Contributing](../CONTRIBUTING.md)
- [Community](COMMUNITY.md)
- [Build from source](BUILD_FROM_SOURCE.md)
- [Security](../SECURITY.md)
- [Roadmap](../ROADMAP.md)
- [Release process](RELEASING.md)

## I want every document

Use the **[complete documentation index](ALL_DOCUMENTATION.md)**.

It is intentionally exhaustive. This page is intentionally short.

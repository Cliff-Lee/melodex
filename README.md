<p align="center">
  <img src="docs/images/melodex.jpg" width="100%" alt="Melodex — explore the music collection you already own.">
</p>

<p align="center">
  <strong>Explore the music collection you already own.</strong>
</p>

<p align="center">
  <a href="https://github.com/Cliff-Lee/melodex/releases/latest"><strong>Download Melodex</strong></a> ·
  <a href="docs/START_HERE.md">Get started</a> ·
  <a href="docs/WHY_MELODEX.md">Why Melodex?</a> ·
  <a href="docs/FAQ.md">FAQ</a> ·
  <a href="docs/README.md">Docs</a> ·
  <a href="docs/TESTING.md">Help test the beta</a>
</p>

# Melodex

Melodex is an **open-source, local-first music player for exploring your music collection, not just searching and playing it**.

Browse your library as a visual album wall, explore relationships between tracks on a music map, and rediscover what you own through listening journeys and interactive playback visuals.

Melodex works with music files you already have, leaves those files where they are, and does not require an account or an AI setup. Connected sources and optional AI controls are there if you want them, but they are not the centre of the experience.

> **Project status:** public beta. The desktop app is the main supported experience; macOS has had the most hands-on testing so far, with packaged Windows and Linux builds also available. Android currently works as a Bridge client. Feedback from real music libraries is especially useful.

## See your collection differently

<p align="center">
  <img src="docs/images/album-wall.webp" alt="Melodex Album Wall showing a visual collection of album artwork">
</p>

<p align="center"><em><strong>Album Wall</strong> — browse by artwork and familiarity instead of treating your library like a spreadsheet.</em></p>

<p align="center">
  <img src="docs/images/music-map.webp" alt="Melodex Music Map showing relationships between tracks">
</p>

<p align="center"><em><strong>Music Map</strong> — pan and zoom through relationships between tracks, then follow the connections that interest you.</em></p>

<p align="center">
  <img src="docs/images/constellation.webp" alt="Melodex Constellation visual playback view">
</p>

<p align="center"><em><strong>Constellation</strong> — make playback itself an exploration surface, with related tracks around what is playing.</em></p>

## Why Melodex is different

- **Browse visually.** Album Wall turns a large collection into something you can scan and wander through.
- **Explore relationships.** Music Map reveals connections between tracks and lets you move through the library spatially.
- **Follow a path instead of shuffling.** Choose Comfort, Explore, or Rediscover, tune how familiar or surprising the session should feel, or build a journey between parts of your collection.
- **Make playback part of discovery.** Interactive visuals such as Constellation keep nearby music within reach while a track is playing.
- **Keep your library yours.** Local files stay where they are. No account, subscription catalogue, server, or AI model is required.

For more detail on the listening experience, see [Why Melodex?](docs/WHY_MELODEX.md).

## Get started

1. [Download the latest release](https://github.com/Cliff-Lee/melodex/releases/latest) for your device.
2. Open **My Music → + Add music** and choose a folder that contains your music.
3. Go to **Home** and choose **Play something**.

You don't need Python, Git, a server, or an AI model to install a release build. Melodex indexes and plays your files where they are; it does not move or copy your music.

| Platform | Install guide |
| --- | --- |
| macOS | [Install on macOS](docs/INSTALL_MACOS.md) |
| Windows | [Install on Windows](docs/INSTALL_WINDOWS.md) |
| Linux | [Install on Linux](docs/INSTALL_LINUX.md) |
| Android | [Android setup](docs/INSTALL_ANDROID.md) — currently pairs with a Melodex Bridge on a computer or home server |

Melodex does not include a subscription music catalogue. A local collection is the best way to use its listening and discovery features; supported connected sources are also available. See [the FAQ](docs/FAQ.md) for details.

## Try the beta

Melodex is still in public beta, and we're looking for everyday listeners. You don't need a huge collection or special expertise. The macOS build has had the most hands-on testing so far; Windows and Linux users are especially useful testers.

If you try it, tell us what was easy, what confused you, whether anything failed, and most importantly whether Melodex gave you a reason to explore something in your collection that you might otherwise have ignored.

**[Follow the 10-minute tester guide](docs/TESTING.md)** · [Send beta feedback](https://github.com/Cliff-Lee/melodex/issues/new?template=tester_feedback.yml) · [Report a problem](https://github.com/Cliff-Lee/melodex/issues/new?template=bug_report.yml)

## Help and community

- [Start Here](docs/START_HERE.md) — install and play your first music.
- [FAQ](docs/FAQ.md) — accounts, AI, music sources, and privacy.
- [Troubleshooting](docs/TROUBLESHOOTING.md) — get help when something goes wrong.
- [Discussions](https://github.com/Cliff-Lee/melodex/discussions) — ask a question or share an idea.
- [Request a feature](https://github.com/Cliff-Lee/melodex/issues/new?template=feature_request.yml).

<details>
<summary><strong>For developers and contributors</strong></summary>

You can use Melodex without building it or knowing how it works internally. If you want to contribute, create an integration, or inspect the technical design, these are the right starting points:

- [Developer Gateway](docs/DEVELOPERS.md) — choose an app, provider, plugin, or API path.
- [5-minute developer quickstart](docs/DEVELOPER_QUICKSTART.md) — fastest route to a working extension/integration setup.
- [Status, stability and trust](docs/developers/00_STATUS_AND_STABILITY.md) — current maturity and compatibility expectations.
- [Ecosystem architecture](docs/developers/01_ECOSYSTEM_ARCHITECTURE.md) — how providers, plugins and external control fit together.
- [Build from source](docs/BUILD_FROM_SOURCE.md) — development environment and build instructions.
- [First contribution](docs/FIRST_CONTRIBUTION.md) — make a change to the project.
- [Provider SDK](provider-sdk/README.md) — create a music-source provider.
- [API documentation](docs/api/README.md) — REST, OpenAPI, MCP, and AI integrations.
- [Full documentation index](docs/ALL_DOCUMENTATION.md) — user and technical references.
- [Source and rights policy](docs/developers/11_SOURCE_AND_RIGHTS_POLICY.md) — requirements for external sources and extensions.

Melodex is open source under the [MIT licence](LICENSE). Music and media accessed through connected sources remain subject to those sources' terms and rights.
</details>

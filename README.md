<p align="center">
  <img src="docs/images/melodex.jpg" width="100%" alt="Melodex — Don't shuffle. Flow.">
</p>


<p align="center">
  <strong>A local-first music player that turns your library into continuous, personalised listening journeys.</strong>
</p>

<p align="center">
  <a href="https://github.com/Cliff-Lee/melodex/releases/latest"><img src="https://img.shields.io/github/v/release/Cliff-Lee/melodex?display_name=tag&sort=semver" alt="Latest release"></a>
  <a href="https://github.com/Cliff-Lee/melodex/actions/workflows/test.yml"><img src="https://github.com/Cliff-Lee/melodex/actions/workflows/test.yml/badge.svg" alt="Tests"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/Cliff-Lee/melodex" alt="MIT licence"></a>
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Android-informational" alt="Platforms">
</p>

<p align="center">
  <a href="https://github.com/Cliff-Lee/melodex/releases/latest"><strong>Download</strong></a> ·
  <a href="docs/VISUAL_TOUR.md">Visual tour</a> ·
  <a href="docs/START_HERE.md">Documentation</a> ·
  <a href="docs/WHY_MELODEX.md">Why Melodex?</a>
</p>

<p align="center">
  <img src="docs/images/play-for-me.png" alt="Melodex Play for Me screen" width="92%">
</p>

---

## Music players choose the next track. Melodex chooses the next direction.

Most players ask:

> What track should play next?

Melodex asks:

> **What should this listening session feel like next?**

It combines your music, your listening history, explicit feedback and — when available — local audio analysis such as tempo, energy, key and structure to make queues feel intentional rather than random.

**Local-first. No subscription required. No AI required.**

---

## Why Melodex?

<table>
<tr>
<td width="50%" valign="top">

### 🌊 Flow

Shuffle treats every ordering as roughly equivalent.

**Flow tries to make one track lead naturally into the next.**

When relevant audio analysis is available, Melodex can consider tempo, energy, key, loudness, timbre and structure. When it is not, it falls back rather than pretending to know more than it does.

</td>
<td width="50%" valign="top">

### 🧠 Taste memory

Melodex quietly learns from how you listen:

- **♥ Love** — strong positive signal
- **Keep** — belongs in your musical world
- completed tracks — positive evidence
- early skips — useful negative evidence
- rediscovery — brings back music you once liked

Taste data is stored locally.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### ↔ Familiar → Surprising

Choose how adventurous a listening session is allowed to become.

Move toward **Familiar** for comfort.

Move toward **Surprising** when you want Melodex to reach further into your collection.

</td>
<td width="50%" valign="top">

### 🔖 Moments

A favourite musical memory is often a point *inside* a track: a breakdown, entrance, lyric, solo or transition.

**Moments** lets you bookmark that exact point and return to it later.

</td>
</tr>
</table>

### ✨ Optional AI, not AI-dependent

Melodex's core player does not require an LLM.

Flow, playback, taste memory and Play for Me work without one. If you connect Ollama, OpenWebUI or another compatible model, natural language becomes another interface to the player:

> Keep this mood, but make the next hour stranger.

> Start familiar, then gradually increase the energy.

> Bring back something I used to like but haven't heard recently.

### 🎧 Rich Now Playing

Playback and music knowledge are deliberately separate. A track can come from any connected audio provider while Melodex enriches it independently with:

- MusicBrainz recording, artist and release identity;
- Cover Art Archive artwork;
- Wikidata-linked Wikimedia Commons artist images when available;
- artist relationships, recording/work credits and release timelines;
- local embedded lyrics, `.lrc` synchronized lyrics and `.txt` sidecars.

Enrichment loads progressively so metadata or artwork lookups do not block playback.

### 🔎 Universal resolution

AI playlists, imported XSPF/M3U playlists and ordinary searches can contain just artist/title/album metadata. Melodex searches connected providers, scores candidate matches, remembers preferred matches and lets you mark a result as **Wrong match** without disabling the whole provider.

The resolver design is inspired in part by [Parachord](https://github.com/Parachord/parachord) and the earlier source-neutral approach pioneered by Tomahawk. Melodex's resolver implementation is independent; see [Third-Party Notices](THIRD_PARTY_NOTICES.md).

---

## See it in action

<table>
<tr>
<td width="50%" align="center"><img src="docs/images/familiar-surprising.png" alt="Familiar to Surprising control"><br><strong>Control how adventurous the session becomes</strong></td>
<td width="50%" align="center"><img src="docs/images/taste-controls.png" alt="Taste controls"><br><strong>Teach Melodex naturally as you listen</strong></td>
</tr>
<tr>
<td width="50%" align="center"><img src="docs/images/moments.png" alt="Moments"><br><strong>Remember exact moments inside tracks</strong></td>
<td width="50%" align="center"><img src="docs/images/ask-melodex.png" alt="Ask Melodex"><br><strong>Optional natural-language control</strong></td>
</tr>
</table>

<p align="center"><a href="docs/VISUAL_TOUR.md"><strong>Take the 5-minute visual tour →</strong></a></p>

---

## Download

You do **not** need Python, Git or developer tools to use a release build.

| Platform | Download | Installation |
| --- | --- | --- |
| macOS — Apple Silicon | `Melodex-macOS-arm64.dmg` | [Guide](docs/INSTALL_MACOS.md) |
| macOS — Intel | `Melodex-macOS-intel.dmg` | [Guide](docs/INSTALL_MACOS.md) |
| Windows 10/11 | `Melodex-Windows-x64-Setup.exe` | [Guide](docs/INSTALL_WINDOWS.md) |
| Windows portable | `Melodex-Windows-portable.zip` | [Guide](docs/INSTALL_WINDOWS.md) |
| Android preview | `Melodex-Android.apk` | [Guide](docs/INSTALL_ANDROID.md) |

<p align="center"><a href="https://github.com/Cliff-Lee/melodex/releases/latest"><strong>Download the latest release →</strong></a></p>

> **Android preview:** Android currently connects to a Provider Bridge running on a Mac, Windows PC, NAS or home server.

---

## How it works

```text
Your music
    ↓
Local library / connected providers
    ↓
Optional audio analysis
    ↓
Taste memory + session intent
    ↓
Flow sequencing
    ↓
A queue designed to go somewhere
```

Melodex is source-neutral. It can work with local files and compatible providers without hard-coding a particular music service into the player.

---

## Providers

Melodex Core implements an open **Melodex Provider Protocol (MPP)**.

- **Built in:** Local Files
- **Reference online source:** Jamendo
- **Desktop:** installable `.mdxprovider` packages
- **Mobile:** authenticated Provider Bridge
- **SDK:** [`provider-sdk/`](provider-sdk/)

Want to build a source integration? Start with the [Provider Development Guide](docs/PROVIDER_DEVELOPMENT.md).

---

## Privacy

Melodex is designed to be local-first.

Listening history, taste memory, Moments and Flow analysis can remain on your device. Nothing needs to be sent to an LLM unless you explicitly configure one and submit a request.

Provider credentials should never be included in LLM context.

[Read the privacy notes →](docs/PRIVACY.md)

---

## Documentation

| I want to… | Start here |
| --- | --- |
| Get running quickly | [Start here](docs/START_HERE.md) |
| See how Melodex works | [Visual tour](docs/VISUAL_TOUR.md) |
| Understand the idea | [Why Melodex?](docs/WHY_MELODEX.md) |
| Install on macOS | [macOS guide](docs/INSTALL_MACOS.md) |
| Install on Windows | [Windows guide](docs/INSTALL_WINDOWS.md) |
| Install on Android | [Android guide](docs/INSTALL_ANDROID.md) |
| Connect an LLM | [LLM guide](docs/LLM_GUIDE.md) |
| Control Melodex over MCP | [MCP control](docs/MCP_CONTROL.md) |
| Understand multi-source matching | [Universal resolver](docs/UNIVERSAL_RESOLVER.md) |
| Inspect/correct a match | [Resolver inspector](docs/RESOLVER_INSPECTOR.md) |
| Use playlist interchange | [XSPF / M3U / M3U8](docs/PLAYLIST_INTERCHANGE.md) |
| Explore Now Playing metadata/lyrics | [Rich Now Playing](docs/RICH_NOW_PLAYING.md) |
| Build a provider | [Provider development](docs/PROVIDER_DEVELOPMENT.md) |
| Build from source | [Build guide](docs/BUILD_FROM_SOURCE.md) |
| Troubleshoot | [Troubleshooting](docs/TROUBLESHOOTING.md) |

---

## Development

Melodex is open source and contributions are welcome.

```bash
git clone https://github.com/Cliff-Lee/melodex.git
cd melodex
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for test commands, project conventions and contribution guidance.

Useful starting points:

- `desktop/` — desktop player
- `android/` — Android client
- `provider-sdk/` — provider SDK and examples
- `docs/` — user and developer documentation
- `scripts/` — release and development tooling

---

## Responsible source policy

Melodex is designed for music that the user is authorised to access.

The public project does not ship source-specific bypass logic, private credentials, copyrighted media or access-control circumvention.

See [RESPONSIBLE_USE.md](RESPONSIBLE_USE.md).

---

## Roadmap

Current priorities include richer provider permissions, additional first-party legal providers, improved local-library indexing, better phrase/beat-grid analysis, transition previews and stronger Android support.

[See the roadmap →](ROADMAP.md)

---

## Acknowledgements & external data

Melodex is MIT-licensed software, but music, artwork and externally fetched metadata are **not relicensed under the Melodex MIT licence**.

- **[Parachord](https://github.com/Parachord/parachord)** — multi-source resolver design inspiration. Parachord is MIT licensed, Copyright © 2025 Jason Herskowitz. Melodex's resolver was independently implemented; the Parachord notice is retained in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) and [`docs/licenses/PARACHORD-LICENSE.txt`](docs/licenses/PARACHORD-LICENSE.txt).
- **[MusicBrainz](https://musicbrainz.org/)** / MetaBrainz Foundation — recording, artist, release, relationship and credit metadata. MusicBrainz core data is CC0; supplementary data is under CC BY-NC-SA 3.0. See the [MusicBrainz data licence](https://musicbrainz.org/doc/About/Data_License).
- **[Cover Art Archive](https://coverartarchive.org/)** — release artwork indexed through MusicBrainz and hosted by the Internet Archive. Cover images remain subject to rights in the underlying artwork; the archive does not provide a blanket Melodex licence for every image.
- **[Wikidata](https://www.wikidata.org/)** — structured artist/image-link data, released under CC0.
- **[Wikimedia Commons](https://commons.wikimedia.org/)** — optional artist images. Each file has its own copyright/licence and attribution requirements; Melodex does not relicense those images.
- **[Jamendo](https://www.jamendo.com/)** — optional reference music provider. Content remains under its individual licence. The provider retains creator/Jamendo attribution, licence information and a direct source-page link.

For fuller notes, see [Third-Party Notices](THIRD_PARTY_NOTICES.md).

---

## Licence

MIT for Melodex code in this repository unless a subdirectory states otherwise. Third-party dependencies retain their own licences. External music, artwork and metadata retain the licences/rights of their respective providers and creators.

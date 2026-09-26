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

## Licence

MIT for Melodex code in this repository unless a subdirectory states otherwise. Third-party dependencies retain their own licences.

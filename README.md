# Melodex

## Don't shuffle. Flow.

**Melodex turns the music you already have access to into continuous, personalised listening journeys.**

Most players ask:

> What track should play next?

Melodex asks:

> **What should this listening session feel like next?**

It combines your music, your listening history, explicit feedback, and — where audio analysis is available — characteristics such as tempo, energy, key and structure to make the queue feel more intentional than ordinary shuffle.

**No subscription required. No AI required. Your listening history can stay local.**

<p align="center">
  <img src="docs/images/play-for-me.png" alt="Melodex Play for Me screen showing session controls and the music player" width="100%">
</p>

**[Download Melodex](https://github.com/Cliff-Lee/melodex/releases/latest)** · **[5-minute visual tour](docs/VISUAL_TOUR.md)** · **[Start here](docs/START_HERE.md)** · **[Why Melodex?](docs/WHY_MELODEX.md)**

---

## Why Melodex?

### Flow instead of shuffle

Shuffle treats every ordering as roughly equivalent.

**Flow tries to make one track lead naturally into the next.**

When the relevant audio is available, Melodex can consider tempo, energy, key, loudness, timbre, intro/outro structure and other local analysis. If deep analysis is unavailable, it falls back rather than pretending to know more than it does.

### A player that learns your taste

Melodex quietly learns from how you listen.

- **♥ Love** — a strong positive signal.
- **Keep** — this belongs in my musical world.
- **Finished tracks** — useful positive evidence.
- **Early skips** — useful negative evidence without treating one skip as hatred.
- **Rediscovery** — brings back music you liked but have not heard recently.

Taste data is stored locally.

### Familiar when you want it. Strange when you don't.

<p align="center">
  <img src="docs/images/familiar-surprising.png" alt="Melodex Familiar to Surprising control" width="100%">
</p>

The **Familiar ↔ Surprising** control changes how adventurous Melodex is allowed to be.

Move toward **Familiar** for comfort. Move toward **Surprising** when you want Melodex to reach further into your collection.

### Remember moments, not only tracks

A favourite musical memory is often a point *inside* a song: an entrance, breakdown, lyric, solo or transition.

**Moments** lets you bookmark that exact point and return to it later.

### AI is optional

Melodex's core player does not need an LLM.

Flow, local playback, taste memory and Play for Me work without one. If you connect Ollama, OpenWebUI or another compatible model, you can also express listening intent naturally:

> Keep this mood but make the next hour stranger.

> Start familiar, then gradually increase the energy.

> Bring back something I used to like but haven't heard recently.

The LLM is another interface to Melodex — not the music engine itself.

---

## See it in five minutes

### 1. Add your music

Open **My music** and choose **Add folder…**.

<p align="center">
  <img src="docs/images/my-music-empty.png" alt="Empty My Music screen with Add folder button" width="100%">
</p>

Melodex indexes the folder without moving your original files.

### 2. Your library appears

<p align="center">
  <img src="docs/images/my-music-library.png" alt="Melodex My Music screen populated with local tracks" width="100%">
</p>

You can play normally, queue tracks, or let Melodex build a session.

### 3. Try Play for Me

Choose a mode, session length, and how adventurous you want the session to be.

<p align="center">
  <img src="docs/images/play-for-me.png" alt="Melodex Play for Me screen" width="100%">
</p>

### 4. Teach it naturally

<p align="center">
  <img src="docs/images/taste-controls.png" alt="Melodex player controls showing Keep, Love and Queue controls" width="100%">
</p>

Use **Keep**, **♥**, complete tracks, or skip things you are not in the mood for. Melodex gradually builds a local taste memory.

### 5. Connect the sources you want

<p align="center">
  <img src="docs/images/sources.png" alt="Melodex Music Sources screen showing local music, Jamendo, provider installation and Provider Bridge" width="100%">
</p>

Melodex itself is source-neutral. The public project ships with Local Files and a Jamendo reference source, plus the open Melodex Provider Protocol for compatible third-party providers.

**[Continue the visual tour →](docs/VISUAL_TOUR.md)**

---

## Install Melodex

You do **not** need Python, Git or developer tools to use a release build.

**[Download the latest release](https://github.com/Cliff-Lee/melodex/releases/latest)**

| Platform | Recommended download | Instructions |
| --- | --- | --- |
| macOS — Apple Silicon | `Melodex-macOS-arm64.dmg` | [Install on macOS](docs/INSTALL_MACOS.md) |
| macOS — Intel | `Melodex-macOS-intel.dmg` | [Install on macOS](docs/INSTALL_MACOS.md) |
| Windows 10/11 | `Melodex-Windows-x64-Setup.exe` | [Install on Windows](docs/INSTALL_WINDOWS.md) |
| Windows portable | `Melodex-Windows-portable.zip` | [Install on Windows](docs/INSTALL_WINDOWS.md) |
| Android preview | `Melodex-Android.apk` | [Install on Android](docs/INSTALL_ANDROID.md) |

> **Android preview:** Android currently connects to a Provider Bridge running on a Mac, Windows PC, NAS or home server.

---

## What can I do with it?

| I want to… | Start here |
| --- | --- |
| Start listening quickly | [5-minute visual tour](docs/VISUAL_TOUR.md) |
| Understand what makes Melodex different | [Why Melodex?](docs/WHY_MELODEX.md) |
| Let Melodex choose music | [Play for Me](docs/VISUAL_TOUR.md#play-for-me) |
| Make a queue feel less random | [Flow](docs/VISUAL_TOUR.md#flow-not-shuffle) |
| Teach Melodex my taste | [Taste controls](docs/VISUAL_TOUR.md#teach-melodex-your-taste) |
| Use natural-language control | [Ask Melodex](docs/VISUAL_TOUR.md#ask-melodex) |
| Add another music source | [Providers](docs/PROVIDER_DEVELOPMENT.md) |
| Listen from Android | [Android installation](docs/INSTALL_ANDROID.md) |

---

## Three ways to use Melodex

**Sunday morning**

> Keep things familiar, low-energy and spacious. Bring back something I haven't heard for a while.

**Driving**

> Start with known music. Gradually increase the energy. Avoid abrupt changes.

**Headphones at night**

> Stay near this mood, but slowly become stranger.

Most of this can be done with Melodex's normal controls. An optional LLM gives you a more expressive way to state the intent.

---

## Privacy

Local listening history, taste memory, Moments and Flow analysis can remain on your device.

Nothing needs to be sent to an LLM unless you explicitly configure one and submit a request. Provider credentials should never be included in LLM context.

---

## Providers

Melodex Core is source-neutral. Providers implement the Melodex Provider Protocol (MPP).

- Built in: **Local Files**
- Reference online source: **Jamendo**
- Desktop: installable `.mdxprovider` packages
- Mobile: authenticated **Provider Bridge**

Developer documentation: [`docs/PROVIDER_DEVELOPMENT.md`](docs/PROVIDER_DEVELOPMENT.md)

Provider SDK: [`provider-sdk/`](provider-sdk/)

---

## Responsible source policy

Melodex is designed for music that the user is authorised to access. The public project does not ship source-specific bypass logic, private credentials, copyrighted media, or access-control circumvention.

See [`RESPONSIBLE_USE.md`](RESPONSIBLE_USE.md).

---

## License

MIT for Melodex code in this repository unless a subdirectory states otherwise. Third-party dependencies retain their own licences.

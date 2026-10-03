# Help test Melodex

Melodex is in active development and we are looking for real listeners to try it on real music libraries.

You do not need to be a developer. The most useful feedback is often simple:

- What was confusing on first launch?
- What did you expect to happen?
- What felt slow, awkward or unreliable?
- What worked surprisingly well?
- Would you keep using Melodex? If not, what would need to change?

## Who we especially want to hear from

Five kinds of testers are particularly valuable right now:

- 🐘 **Huge libraries** — 50,000+ tracks, especially 100k–1M+
- 🌐 **NAS / network collections** — SMB, NFS, mounted shares and slower or unreliable storage
- 🪟 **Windows users** — installation, scanning, playback and normal day-to-day use
- 🐧 **Linux users** — AppImage/package behaviour and different desktop setups
- 🧪 **Messy metadata collections** — missing tags, duplicates, odd encodings, unusual artwork and mixed formats

Apple Silicon and Intel Mac feedback remains welcome too. So does feedback from people who normally use Spotify, Apple Music, YouTube Music, foobar2000, MusicBee or similar players, and from accessibility or keyboard-navigation users.

You do not need a huge collection. A fresh-user experience with only a few albums is useful because it tests whether Melodex is understandable, not just whether it scales.

## 10-minute test

1. [Download the latest release](https://github.com/Cliff-Lee/melodex/releases/latest).
2. Launch Melodex.
3. Add a music folder from **My Music → + Add music**.
4. Play an album or track.
5. Try **Home**, **Explore**, **Flow**, **Playlists**, and one visual feature such as Album Wall or Music Map.
6. Notice anything that makes you stop and think: “What am I supposed to do here?”
7. Tell us about it.

## Where to leave feedback

- [Something broke → Bug report](https://github.com/Cliff-Lee/melodex/issues/new?template=bug_report.yml)
- [Something should work differently → Feature request](https://github.com/Cliff-Lee/melodex/issues/new?template=feature_request.yml)
- [General beta experience or stress test → Beta Test Report](https://github.com/Cliff-Lee/melodex/issues/new?template=tester_feedback.yml)
- Discussions are the best place for open-ended questions and ideas.

Screenshots are welcome when they help explain a UI problem. Please do not post copyrighted music files, passwords, API keys, tokens, private URLs, or other secrets.

## Useful details

If something goes wrong, include:

- Melodex version
- operating system and version
- Apple Silicon / Intel where relevant
- approximate library size
- file types involved, such as MP3, FLAC, M4A or WAV
- exact steps that caused the problem
- what you expected instead

For source/plugin issues, Melodex can export redacted diagnostics from **Sources → Show power tools → Export diagnostics…**. Review the file before posting it.

## What happens to feedback?

Reports are public on GitHub so other testers can confirm the same problem, add details and follow progress. Small observations are useful; you do not need to write a formal bug report.

Thanks for helping make Melodex better for people who were not involved in building it.

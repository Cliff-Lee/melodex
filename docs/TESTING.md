# Help test Melodex

Melodex is in active development and we are looking for real listeners to try it on real music libraries.

You do not need to be a developer. The most useful feedback is often simple:

- What was confusing on first launch?
- What did you expect to happen?
- What felt slow, awkward or unreliable?
- What worked surprisingly well?
- Would you keep using Melodex? If not, what would need to change?

## Who we especially want to hear from

The macOS build has had the most hands-on testing so far. We especially welcome:

- Apple Silicon Mac users with small, large or messy local libraries
- Intel Mac users
- Windows users
- Linux users
- people with large FLAC/MP3 collections
- people with incomplete tags or missing artwork
- people who normally use Spotify, Apple Music, YouTube Music, foobar2000, MusicBee or similar players
- accessibility and keyboard-navigation users

You do not need a huge collection. A fresh-user experience with only a few albums is useful too.

## Choose a test path

For most people, use the **10-minute listener test** below. If you have a large
collection or music on a NAS/network share, use the dedicated
[large-library/NAS retest](LARGE_LIBRARY_BETA_RETEST.md) as well.

## 10-minute listener test

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
- [General beta experience → Tester feedback](https://github.com/Cliff-Lee/melodex/issues/new?template=tester_feedback.yml)
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

For source/plugin and large-library issues, Melodex can export redacted diagnostics from **Sources → Show power tools → Export diagnostics…**. Review the file before posting it.

If your music is on a NAS/network share, also tell us the storage type (for
example Synology/QNAP/server), the protocol if you know it (SMB/NFS), and
whether the problem happened during first import, restart, rescan or playback.

## What happens to feedback?

Reports are public on GitHub so other testers can confirm the same problem, add details and follow progress. Small observations are useful; you do not need to write a formal bug report.

Thanks for helping make Melodex better for people who were not involved in building it.


## What we are especially validating now

Recent beta work specifically targets:

- very large local/NAS libraries;
- keeping the UI responsive while indexing;
- restart from the persistent library index;
- fast unchanged rescans without rereading every tag;
- package size and installation reliability across macOS, Windows and Linux;
- macOS trust/signing readiness.

The permanent automated stress case is **12,700 tracks**. Synthetic CI does not
replace real collections, so reports from people with messy tags, unusual file
layouts and network storage remain especially valuable.

For maintainers preparing a beta build, see
[Public beta release checklist](BETA_RELEASE_CHECKLIST.md).

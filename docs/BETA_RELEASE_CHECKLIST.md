# Public beta release checklist

Use this before promoting a Melodex build beyond routine development testing.

The aim is simple: a tester should be able to download Melodex, understand what
kind of build they have, add music, report a problem, and give us enough
information to reproduce it without needing to know the codebase.

## 1. Release engineering

- [ ] version metadata matches the intended tag
- [ ] normal desktop tests pass
- [ ] macOS Intel, macOS Apple Silicon and Windows frozen builds pass
- [ ] Linux `.deb` and AppImage smoke tests pass
- [ ] the 12,700-track large-library acceptance workflow passes
- [ ] desktop size-regression guards pass
- [ ] macOS trust report has been reviewed
- [ ] once Campaign 9B is activated, macOS release artifacts are Developer ID
      signed, notarized, stapled and Gatekeeper accepted

## 2. Fresh-user installation

Test the actual release artifact, not a source checkout.

### macOS

- [ ] correct Intel/Apple Silicon download is obvious
- [ ] DMG opens and Melodex can be dragged to Applications
- [ ] first launch behaviour matches the trust status reported by CI
- [ ] no Python, Homebrew or Terminal step is required for ordinary playback

### Windows

- [ ] installer completes normally on a clean user account
- [ ] portable ZIP launches without a developer environment
- [ ] uninstall does not remove the user's separate Melodex data directory

### Linux

- [ ] `.deb` installs on a supported Ubuntu/Debian system
- [ ] AppImage launches after setting its executable bit
- [ ] packaged launch smoke remains green on the maintained distro matrix

## 3. Ten-minute listener path

A tester should be able to complete this without reading developer docs:

1. install Melodex;
2. add a small music folder;
3. play an album or track;
4. use Home / Play something;
5. try Flow;
6. open Now Playing / Lyrics;
7. try one spatial feature such as Album Wall or Music Map;
8. find the feedback/reporting route.

Record any point where the tester asks what they are supposed to do next.

## 4. Large-library path

For testers with large or network collections, use
[LARGE_LIBRARY_BETA_RETEST.md](LARGE_LIBRARY_BETA_RETEST.md).

The permanent stress case is approximately **12,700 tracks / 500 GB on NAS
storage**. A beta should not be promoted as having solved the original import
failure until both the automated acceptance gate and at least one real network
library retest have passed.

## 5. Feedback quality

- [ ] tester feedback template asks for platform and Melodex version
- [ ] library size and storage type can be reported
- [ ] bug template includes enough reproduction detail
- [ ] users are told how to export redacted diagnostics
- [ ] issue forms warn against posting credentials, tokens, private URLs or music
- [ ] release notes point testers to the correct feedback route

## 6. Public-facing claims

Before publishing:

- do not call a Mac build notarized unless the trust report confirms it;
- do not claim a specific large-library performance time from synthetic CI;
- distinguish local files from connected/streaming sources;
- explain that Melodex indexes local/NAS audio where it already lives rather
  than copying the collection;
- keep AI optional in listener-facing copy.

## 7. Suggested beta feedback question

The most useful closing question is:

> What stopped you from treating Melodex like a music player you would actually
> keep installed?

That tends to surface installation friction, trust, missing basics, confusing
navigation and performance problems better than asking only for feature ideas.

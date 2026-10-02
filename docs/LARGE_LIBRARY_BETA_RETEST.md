# Large-library / NAS beta retest

This checklist is for the real-world stress case that originally exposed the
library-scan freeze:

> approximately **12,700 FLAC files / 500 GB** on a Synology NAS.

The goal is not just "does the import finish?" The retest should confirm that
Melodex stays usable before, during, after and between scans.

## 1. First import

1. Connect/mount the NAS normally.
2. Launch Melodex.
3. Add the NAS music folder from **My Music → + Add music**.
4. During indexing, confirm:
   - the window remains responsive;
   - navigation still works;
   - progress moves from discovering files to reading metadata;
   - Melodex states that it indexes files where they live and does not copy them.
5. Let the first scan complete.
6. Confirm the expected library appears.
7. Export **redacted diagnostics**.

Record roughly how long the first import took. Exact timing is informative, not
a pass/fail criterion because NAS/network performance varies.

## 2. Restart test

1. Quit Melodex normally.
2. Leave the NAS mounted.
3. Reopen Melodex.
4. Confirm the indexed library appears promptly from the local SQLite index.
5. Confirm Melodex does not automatically reread 12,700 FLAC tags on startup.

## 3. Unchanged rescan

1. Choose **Rescan** without changing any music files.
2. Let it complete.
3. Export diagnostics again.

For an unchanged, fingerprinted library, the expected result is:

- metadata reads: **0**
- metadata reused: approximately the full library
- index rows rewritten: **0**

The filesystem still has to enumerate/stat files, so the rescan is not expected
to be instantaneous over a NAS.

## 4. Cancel test

1. Start another rescan.
2. Cancel while it is active.
3. Confirm Melodex remains responsive.
4. Confirm the previously completed library remains visible.
5. If the NAS itself is stuck in an OS/network call, confirm cancellation still
   returns control after the scan worker is terminated.

## 5. NAS offline test

1. Quit Melodex.
2. Disconnect/unmount the NAS.
3. Reopen Melodex.
4. Confirm the cached library is still browsable.
5. Confirm startup does not hang waiting for the NAS.
6. Reconnect the NAS and rescan.

Playback naturally requires the original audio file to be reachable.

## 6. What to send back

Please attach:

- the Melodex version;
- Mac/Windows/Linux and CPU architecture;
- NAS model and connection type if known (SMB/NFS/etc.);
- whether each of the five sections above passed;
- the exported redacted diagnostics JSON after the first scan and unchanged
  rescan.

If Melodex becomes unresponsive, a macOS **Sample Process** capture is also very
useful. The diagnostics export is designed to omit local library paths,
credentials, tokens, stream URLs and media filenames.

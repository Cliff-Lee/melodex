# Next release — draft notes

**Development after Melodex v0.7.7.**

Current development version: **0.7.8.dev0**.

This file tracks changes intended for the next release after **v0.7.7**.

No post-v0.7.7 campaigns have been added yet.


## Crash hardening

- Replaces per-task temporary PySide `QObject` signal bridges with one long-lived
  QApplication-owned UI dispatcher. This closes a queued-event lifetime race that
  could leave a posted Qt MetaCall event targeting a Python wrapper after the
  wrapper had already been collected.
- Late background completions after the main window starts closing are now safely
  discarded through the persistent dispatcher.

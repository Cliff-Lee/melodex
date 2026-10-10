# Next release — draft notes

Current target version: **0.7.29**.
Previous stable release: **0.7.28**.

This is the v0.7.29 macOS startup hotfix. It prevents an early `WindowStateChange` event during geometry restoration from referencing `playback_feature` before initialization. See `docs/releases/v0.7.29.md` for the public release notes and testing guidance.

Native iPhone support remains deferred; Google Play publication remains outside current release work.

# Code-health guardrails — Campaign 12 / P12b

P12b adds lightweight quality ratchets before production-code refactoring begins.

## Principles

The first guardrails are intentionally conservative:

- catch high-confidence correctness problems;
- stop the largest structural hotspot from growing;
- avoid mass reformatting;
- avoid turning historical style debt into hundreds of unrelated changes;
- add no runtime dependency;
- preserve the startup, responsiveness, NAS and large-library contracts.

## Desktop Ruff

The desktop project now declares Ruff as a development dependency and configures a small initial ruleset:

- `E9` — syntax/runtime parser-class errors;
- `F63` — invalid comparison/assertion constructs;
- `F7` — invalid control-flow constructs;
- `F82` — undefined names and invalid exports.

This is a correctness gate, not a style gate. Import sorting, formatting, naming and broad cleanup rules are intentionally deferred until the affected debt can be handled in focused PRs.

The first CI run found three pre-existing F821 findings. P12b records those exact path/code/message/source-line fingerprints in `scripts/ruff_baseline.json` rather than ignoring F821 for entire files. `scripts/ruff_guardrail.py` fails if Ruff reports anything outside that known set. If an existing issue is fixed, the gate reports the stale baseline entry so it can be removed.

This gives P12b the intended ratchet: historical debt may remain temporarily, but new correctness debt is rejected.

The provider SDK already has its broader Ruff configuration; P12b does not weaken it.

## MainWindow ratchet

`scripts/codebase_guardrails.py` records the P12a baseline for:

    desktop/melodex/main_window.py <= 7629 physical lines

The number is not a target. It is a one-way ceiling.

P12c should lower the ceiling whenever responsibilities are extracted. New feature work should not make the file larger again.

If a future change trips the ratchet, the expected response is to move responsibility out of `MainWindow`, not increase the limit.

## CI

The Tests workflow gains a separate **Code health guardrails** job which:

1. installs Ruff only as CI/development tooling;
2. runs the desktop correctness-oriented Ruff rules against the exact-debt baseline;
3. checks the structural ratchet.

Keeping this as a separate job makes failures easy to interpret and avoids coupling lint tooling to runtime dependencies.

## P12b exit criterion

P12b is complete when the guardrail job is green without production-code changes or mass formatting.

After that, P12c may begin responsibility-led extraction from `MainWindow`.

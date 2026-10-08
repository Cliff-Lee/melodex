# P18 — Private Taste Engine

## Purpose

P18 makes Melodex's local listening memory a useful, inspectable taste model.
It should improve session choices while keeping music history on the listener's
device, separating lasting preferences from recent listening context and the
amount of exploration requested for the current session.

No training step blocks playback. A listener can ignore the model and keep
choosing tracks, routes, and queue edits directly.

## Campaign stages

1. **P18a — Separate taste layers.** Derive identity signals from explicit
   feedback and completed listening, report recent context separately, and keep
   the current exploration request distinct from both.
2. **P18b — Apply the model to sessions.** Use confidence-weighted artist and
   genre evidence as a bounded adjustment to local session ranking. Explain a
   match in the Up Next queue, and preserve an explicit track dislike as a hard
   exclusion.
3. **P18c — Make correction direct.** Add clear “More like this” and “Less like
   this” controls that update the same local model as existing Like, Keep, and
   Not for me actions.
4. **P18d — Improve cold-start learning.** Learn cautiously from early listens
   and distinguish recent session reactions from durable preferences. Keep
   first playback independent of profile completeness.
5. **P18e — Share one local model across listening surfaces.** Carry the same
   inspectable taste signals into Living Queue, Rediscover, Music Map, Journeys,
   and recipes without copying history into provider or external AI requests.
6. **P18f — Calibrate and qualify.** Test sparse metadata, small and large
   libraries, contradictory feedback, cold starts, privacy boundaries, and
   understandable explanations.

Each stage must pass its focused tests before the next stage starts.

## P18a–b progress

`taste_model.py` builds three separate layers from local data:

- **Identity** uses explicit love, keep, and dislike feedback plus completed
  listens. Play counts alone have very low weight. The aggregate skip counter
  is not treated as a lasting preference because it has no session timestamp.
- **Context** summarizes up to 20 recent local plays independently from the
  identity profile. It exposes artist and genre counts, not paths or absolute
  timestamps.
- **Exploration** records the current session's Familiar/Surprising slider
  value and label. It does not rewrite identity taste.

The profile is generated in memory from existing UserState data. There is no
schema migration, background scan, external service, or required training
session. The profile summary shown on Home is bounded and path-free; it names a
couple of learned artists or genres and says the profile stays on this device.
Existing Play for Me scoring now applies a small confidence-weighted
artist/genre adjustment, and Up Next surfaces the model's reason in its existing
“Why this track” detail. An explicit track-level Not for me signal still
overrides a positive profile match.

The P18a–b focused gate is `desktop/tests/test_taste_model.py`. It covers
durable versus aggregate skip evidence, independent profile layers, path
redaction, cold-start neutrality, local session scoring, visible reasons, and
explicit dislike precedence.

## P18c progress

The player bar now has one **Taste** menu with **More like this**, **Less like
this**, and **Clear taste correction** actions. More/Less apply to the current
track's artist and tagged genres. Repeating an action on the same track updates
that correction instead of multiplying it; choosing the opposite action changes
it, and Clear removes it. Tracks without artist or genre details cannot create
a broad correction.

Corrections live in the existing local preferences store. Their keys are
hashed track identities, and their values contain only the direction, artist,
and genre labels. They add strong explicit evidence to the same confidence
model used by Play for Me. Home and Up Next continue to explain what the model
learned and why a candidate fits. No extra database table or network call is
introduced.

P18c coverage in `desktop/tests/test_taste_model.py` checks persistence,
reversibility, per-track idempotence, path exclusion, score direction, and
reasons. A Qt test in `desktop/tests/test_playback_feature.py` checks the menu
actions and their save/clear behavior.

## P18d progress

The latest local listening session now contributes its own reaction layer.
Completed tracks count as small positive evidence; an incomplete track counts
as a quick skip only when the next track started within the same 30-second
window Melodex uses for skip feedback. Reactions decay by age and expire after
14 days. They influence Play for Me with a bounded adjustment and a separate
queue explanation, while staying distinct from the durable identity profile.
The current track is neutral until a completion or a quick skip is recorded.
An empty profile does not block the first Play for Me session.

P18d adds no database table or migration. Session reactions are derived in
memory from local listening history, and profile/Home output exposes only
bounded artist and genre summaries and aggregate reaction counts. Tests cover
completed versus skipped reactions, identity separation, path redaction,
explanations, and cold-start playback.

## P18e progress

`build_local_taste_model()` is now the shared Core entry point for Play for Me,
the inspectable profile, Rediscover reranking, and Music Map. Rediscover applies
the bounded taste adjustment only after the extension returns; the new
correction and recent-session layers stay inside Core and are not added to the
extension snapshot. The snapshot schema and its existing path redaction remain
unchanged.

Music Map nodes carry the same bounded match and its reason. Familiar,
Forgotten, and Surprising journey stages use that signal and include its reason
in the route explanation. Journey Live passes those explanations into Living
Queue, while Play for Me continues to pass its explanation directly. Recipes
store route intent and selectors only; loading or replaying a recipe uses the
current local Music Map model without embedding listening history in the
recipe.

## P18f progress

Focused tests cover sparse and missing metadata, contradictory artist feedback,
small-library cold starts, bounded profiles from large inputs, privacy
redaction, plugin snapshot stability, positive and negative explanations, and
explicit dislike precedence. Model output stays bounded to eight identity
artists and genres, five recent context entries per type, and five recent
session entries per type.

## Completion gates

P18 is complete when session choices improve from local history without hiding
the controls that shaped them, the listener can directly correct its taste
model, cold start remains immediate, profile explanations are understandable,
and taste data stays local unless the listener deliberately sends a request to
an explicitly configured external service.

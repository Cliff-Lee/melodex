# P17 — Rediscovery Engine

## Purpose

P17 helps listeners find worthwhile music that has faded from view. It combines
private listening history with the structure already present in a local music
library, then surfaces those signals in the player and listening tools.

Rediscovery must work on a fresh install. Listening history should make its
suggestions more personal over time, but a new listener should still get useful
routes from album order, artist coverage, and library structure.

## Campaign stages

1. **P17a — Build rediscovery signals.** Combine per-track play and feedback
   history with local metadata such as album membership, track order, and
   artist coverage. Keep a useful metadata-only path when play history is empty.
2. **P17b — Resurface forgotten favourites and neglected artists.** Rank loved,
   kept, completed, and skipped music with recency and artist-level memory.
3. **P17c — Explore hidden gems and deep cuts.** Find unplayed parts of known
   albums, deep cuts, and underexplored albums without over-relying on tags.
4. **P17d — Add listening time travel.** Let listeners revisit meaningful
   periods and sessions from their own history.
5. **P17e — Connect the music surfaces.** Carry rediscovery signals into Music
   Map, Journeys, and Living Queue so suggestions remain steerable in context.
6. **P17f — Polish and qualify.** Make the reasons understandable, keep large
   libraries responsive, and test sparse metadata, new installs, and mature
   listening histories.

## P17a progress

The local session planner now receives a bounded metadata signal alongside its
existing per-track history. It recognizes album gaps, ordered deep cuts, and
tracks from artists already present in listening history. The Rediscover route
uses those signals when there are no plays to score, and labels metadata-backed
choices plainly. Missing album or track-order tags produce a neutral score so
the existing new-to-you selection remains available.

The P17a gate is the focused rediscovery signal and planner test suite, plus the
existing Mind and Music Map tests. Signals are calculated in memory from the
current catalog and local UserState; there is no schema migration or network
dependency.

## P17b progress

Rediscover now keeps a well-liked track eligible after a longer absence, with
recently played tracks still receiving a strong repetition penalty. It also
aggregates plays, completions, skips, loves, keeps, and last-played time by
artist. An unplayed track can therefore surface as a return to a favourite
artist that has been quiet for a while. The recommendation reason distinguishes
that path from a previously played favourite and from a metadata-only deep cut.

The focused P17b checks cover old versus recent favourites and an unheard track
from a neglected favourite artist. Artist memory is computed from local
UserState and affects the Rediscover route only.

## P17c progress

The signal builder now rates album memory from completed, loved, and kept
tracks, then connects that evidence to unplayed deep cuts on the same album.
Those tracks receive a hidden-gem boost and a reason that says which album
signal helped. Album familiarity and track order are both required; a lone
track with missing order metadata does not get called a deep cut.

The focused P17c test compares a deep cut from an album with a loved track
against an equally deep cut from an album with no listening evidence. Sparse
metadata continues to use the neutral fallback.

## P17d progress

Memory Atlas now replays a selected session, album, week, or year from its
recorded play order. Double-clicking an island starts the replay; keyboard
users can select islands with the arrow keys and press Enter. The renderer
holds only opaque local history IDs, while the playback layer resolves those
IDs to queue entries. Replay is capped at 200 tracks per activation so a broad
time period cannot create an unbounded queue.

The listening history query and grouping remain in the existing background
visual-context task. Playback uses the manual queue intent so the captured
historical order is preserved, and the local file paths never enter the visual
mark or its renderer.

## P17e progress

Music Map now combines the P17 library score with its existing recent-favourite
signal. Strong hidden gems, album gaps, and artist returns can therefore stay
visible in the Rediscovery lens even when they have no recent play signal. The
map exposes the reason on hover and selection, and Forgotten journey stages
carry that reason into their fit explanation. Journey Live steers against the
same map values; Living Queue's Rediscover route already uses the shared P17
signal builder through MindEngine.

The map derives signals from the bounded local catalog and UserState snapshot
inside its existing background task. It adds no scan to startup or the playback
path, and introduces no schema or network dependency.

## Completion gates

P17 is complete when a fresh install can start a useful rediscovery route, a
listener's history makes it more personal, the choice reasons are clear, and
all integrated surfaces stay responsive on large libraries. Each stage must
pass its focused tests before the next stage starts.

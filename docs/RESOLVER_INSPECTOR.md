# Resolver Inspector and Match Memory

Melodex can resolve one requested song across several connected providers. The Resolver Inspector makes that decision visible and correctable.

## Open the inspector

Start a track, then choose **Match** in the player bar. Melodex searches the connected providers and shows ranked candidates.

Each row includes:

- overall confidence;
- provider and provider priority;
- artist, title and album;
- title / artist / album similarity;
- duration difference when both sides provide duration;
- version flags such as `live`, `remix`, `cover` or `acoustic`;
- a short explanation of the score.

The resolver still refuses to auto-play candidates below its confidence threshold.

## Actions

### Play this match

Use the selected candidate now without changing long-term match memory.

### Prefer

Use the selected candidate now and remember it for this requested song. On future resolves, Melodex tries the preferred provider result first. The preference is specific to that song; it does not globally prioritize the provider.

### Wrong match

Block only the selected provider result for this requested song. The provider remains enabled, and the same source result can still be valid for a different requested song. Melodex immediately re-resolves the request and tries the next acceptable candidate.

If the rejected result had previously been preferred, that preference is removed automatically.

### Reset memory

Clear the preferred match and wrong-match blocks for this requested song only.

## Storage

Match memory is stored in Melodex's existing `sources.json` settings file:

- `resolver_preferences`
- `resolver_blocklist`

Only resolver identity/metadata is stored. Melodex does not persist expiring stream URLs as preferred matches.

## AI / MCP

The same resolver transparency is available through MCP:

- `melodex_resolution_candidates`
- `melodex_prefer_match`
- `melodex_wrong_match`
- `melodex_reset_match_memory`

This lets an external assistant inspect or correct a source match without bypassing the resolver.

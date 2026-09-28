# Developer Glossary

**Capability** — one thing an extension can do, such as playback or artwork lookup.

**Canonical identity** — cross-provider identity such as a MusicBrainz recording ID or ISRC.

**Provider-local identity** — an ID meaningful only to one provider.

**MPP** — Melodex Provider Protocol.

**.mdxprovider** — ZIP-compatible provider package.

**Capability Broker** — Core component that discovers suitable extensions and routes capability calls.

**Enrichment** — additional data attached to an already usable entity, such as metadata, artwork or lyrics.

**Provenance** — information recording where an external contribution came from.

**Playback resource** — current playable URL/file/HLS resource plus relevant request state.

**Fixture** — saved upstream response used for deterministic offline testing.

**Registry** — discoverability index for extensions; it does not need to host the extension itself.


**Registry-verified package** — an install whose downloaded bytes matched registry byte-size/SHA-256 metadata and whose package-declared ID/version matched the registry entry. This is not publisher signing.

**Manual install** — a user-selected local package. Melodex may record its local hash, but there is no registry digest/publisher record to compare it with.

**Reviewed registry entry** — a registry status showing that the project applied its current technical/source-policy review. It is not a guarantee of every upstream media item.

**Signed publisher** — cryptographically identified package publisher. This is a planned concept and is not implemented in the current ecosystem.

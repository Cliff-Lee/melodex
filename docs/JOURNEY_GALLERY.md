# Journey Recipe Gallery

The **Journey Recipe Gallery** is the discovery layer for reusable Melodex journeys.

Open:

**Journeys → Explore gallery…**

The Gallery is intentionally simpler than the Plugin Directory because Journey Recipes are validated data, not executable code.

## What you can browse

Each Gallery entry shows:

- Recipe name;
- author;
- version;
- description;
- tags;
- routing mode;
- ordered stage preview;
- license;
- source repository;
- registry status;
- compatibility;
- SHA-256;
- whether the Recipe is already in your local Journey Library.

Search covers names, authors, descriptions and tags.

The tag filter can narrow the Gallery to ideas such as:

- focus;
- night;
- rediscovery;
- discovery;
- calm;
- rhythmic;
- bright;
- energy.

## Add to Library

Choose a Recipe and press **Add to Library**.

Before saving anything, Melodex:

1. validates the Recipe schema;
2. calculates the SHA-256 of canonical Recipe JSON;
3. compares it with the registry entry;
4. checks Melodex / Recipe-schema compatibility;
5. rejects blocked entries.

The Recipe is then saved to your normal local Journey Library.

Adding Gallery data does **not** execute third-party code.

## Updates

Gallery Recipes use stable registry IDs.

If a local Gallery copy differs from the current registry hash, the Gallery shows **UPDATE** and can replace that local Gallery copy.

A matching copy shows **ADDED**.

Personal Recipes created directly in Journey Library remain separate.

## Online registry and offline fallback

The public registry is stored in this repository:

```text
journey-recipes/registry.json
```

The desktop app normally checks the GitHub-hosted registry and caches valid results.

If the network is unavailable:

- a valid recent cache can be used;
- otherwise Melodex falls back to a bundled starter Gallery.

The bundled fallback and canonical repository registry are checked for equality in CI.

## Starter Gallery

The first project examples are:

- **Deep Work Arc** — Calm → Rhythmic → Familiar → Energetic
- **Late Night Descent** — Familiar → Darker → Calm → Forgotten
- **Rediscovery Sunday** — Familiar → Forgotten → Bright
- **Dark to Bright** — Darker → Rhythmic → Energetic → Bright
- **Discovery Drift** — Calm → Surprising → Darker → Bright

They use semantic stages only, so they can adapt to each user's own library.

## Trust model

A valid Gallery entry means:

- the Recipe matches the supported schema;
- its canonical bytes match the registry SHA-256;
- its compatibility metadata is acceptable.

It does **not** mean:

- the author's legal identity was cryptographically verified;
- every listener will get the same tracks;
- Melodex endorses a named artist or musical taste;
- the Recipe definition grants rights to music referenced by exact waypoints.

## Community publishing

Community Recipes are added through normal GitHub pull requests.

See:

[Journey Recipe registry contribution guide](../journey-recipes/README.md)

The contribution workflow is intentionally serverless: GitHub hosts the registry, source history, pull-request review and public provenance.

## Why Recipes are different from plugins

A Plugin extends Melodex behavior.

A Recipe expresses listening intent.

```text
Plugin
  executable capability

Recipe
  validated journey data
```

Keeping them separate allows community sharing without asking users to install executable code merely to try somebody else's listening idea.

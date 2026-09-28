# Melodex Governance

Melodex is currently a **maintainer-led open-source project**.

The project is still young, so governance is deliberately lightweight. This document describes how decisions are made today rather than pretending a larger formal organization already exists.

## Current maintainer

The current repository is maintained by **Cliff-Lee**, the repository owner.

That does not mean every idea, plugin, source, or contribution is personally endorsed by the maintainer.

## Where decisions happen

Normal technical/project decisions should be visible in public project history:

```text
issue / proposal
      ↓
discussion
      ↓
pull request
      ↓
tests / review
      ↓
merge or documented rejection
```

Small fixes and documentation improvements may go directly to a pull request.

Substantial protocol, security, architecture, registry-policy, or compatibility changes should normally start with an issue or proposal.

Security-sensitive matters are the exception and should use the private process in [SECURITY.md](SECURITY.md).

## Registry decisions

The Plugin Directory registry is curated through version-controlled registry changes.

Registry labels have specific meanings:

- `example` — project/reference example;
- `community` — community-published, without a claim of project review;
- `reviewed` — passed the project's current technical/source-policy review;
- `deprecated` — retained for continuity but no longer recommended;
- `blocked` — should not be offered for installation.

A registry status is not payment, sponsorship, legal advice, cryptographic publisher identity, or a guarantee about every item returned by an upstream service.

Status changes should be reviewable in repository history.

See [Registry governance](docs/developers/17_REGISTRY_GOVERNANCE.md).

## Conflicts and affiliations

When proposing an integration, registry entry, or policy change involving a service you work for, represent, are paid by, or have another material relationship with, disclose that relationship in the issue or pull request.

The point is transparency, not exclusion.

## Compatibility and deprecation

Melodex is still pre-1.0 software.

Breaking changes should be called out clearly in changelogs/documentation and should include migration guidance when practical.

The current maturity picture is maintained in [Status, stability and trust](docs/developers/00_STATUS_AND_STABILITY.md).

## Community growth

If the project gains multiple regular maintainers, release managers, or registry reviewers, this governance document should evolve to name roles, review thresholds, and decision/appeal procedures explicitly.

The governance model should follow the real community, not get ahead of it.

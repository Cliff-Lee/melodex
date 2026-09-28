# Terminology and Claim Policy

Melodex is developed in public. Words that imply trust, maturity, security, distribution, or endorsement should describe a specific property rather than act as marketing shorthand.

This page defines the preferred vocabulary.

## Maturity

Use the status labels from [Status, stability and trust](00_STATUS_AND_STABILITY.md):

| Term | Meaning |
| --- | --- |
| **Implemented** | Present in the current public repository and exercised by tests |
| **Preview** | Implemented, but compatibility may still change before a stable commitment |
| **Experimental** | Implemented for real use/testing, but its contract is deliberately still evolving |
| **Planned** | Design direction; do not imply that users can use it today |
| **Historical** | Retained design/migration record, not current implementation guidance |

Do not call MPP or the Provider SDK **stable** today. MPP 1.0 remains a preview compatibility target and the SDK remains 0.x.

### “Stable” is still valid for identity

A **stable ID** means an identifier should remain consistent for the same entity.

That is different from claiming a protocol/API has a stable compatibility commitment.

## Distribution

### Built into the app

Use **built into the desktop app** only for functionality/source integrations that are part of the application itself.

Examples include Local Files and the Jamendo reference integration.

Do not use “built in” merely because source code or a package exists somewhere in the repository.

### Project-maintained reference integration

Use this for example/reference provider or extension code maintained by the Melodex project.

It means:

- the Melodex project maintains the integration;
- it exists to demonstrate the public extension boundary;
- it does not create a special security or rights guarantee.

The repository currently contains an Internet Archive project-maintained reference provider under the historical directory name `official-providers/`.

The directory name is repository organization, not a registry trust status.

### Registry example

An entry with registry status `example`.

It is useful for learning/testing. It is not automatically a `reviewed` registry entry.

### Community registry entry

An entry with registry status `community`.

It is community-published and must not be described as Melodex-reviewed.

## Trust and verification

### Registry-verified package/install

Use **registry-verified** only when Melodex has checked:

```text
downloaded byte size
+
SHA-256
+
package-declared ID
+
package-declared version
```

against the registry entry.

This is an integrity/identity-consistency check against registry metadata.

It does **not** mean:

- publisher identity was cryptographically proved;
- the package was fully audited;
- the upstream service is endorsed;
- every media item has the same rights;
- the code is sandboxed.

Avoid vague phrases such as **verified package** or **hash-verified package** when the precise term is **registry-verified package**.

### Reviewed registry entry

Use **reviewed registry entry** for registry status `reviewed`.

It means the project applied its current technical/source-policy review.

It is not a warranty, certification, legal opinion, or endorsement of every result produced by the upstream service.

### Manual install

A package selected directly by the user.

Melodex can record its local hash, but there is no registry package record to verify it against.

### Signed publisher

A cryptographically identified publisher/package-signing model.

**Not implemented today.**

Do not use “signed publisher”, “verified publisher”, or equivalent language for current third-party packages except when explicitly describing future work.

## Security

### Out-of-process / failure isolation

Current desktop providers/extensions run outside the GUI process.

This improves crash, timeout, and protocol-failure isolation.

### Sandbox

Do **not** call current plugins sandboxed.

A separate process is not a complete OS sandbox. Third-party plugin processes currently run with the operating-system permissions of the user unless the surrounding OS/container supplies stronger restrictions.

### Authenticated

Use **authenticated** when an API requires the correct bearer token or other authentication mechanism.

Authentication does not automatically imply transport encryption.

For example, a bearer-token LAN API over plain HTTP is authenticated but should not be described generically as “secure over the internet”.

### Safe / secure

Prefer the property being claimed:

- `allowlisted model context fields`, not “safe fields”;
- `metadata-only fallback`, not “safe ordering”;
- `path-traversal checks`, not “secure extraction”;
- `bearer-token authenticated`, not simply “secure”.

## Source and rights language

### Reference/example does not mean blanket rights

A source integration can be legal/open as an example while individual upstream items still have item-specific rights.

Use wording such as:

> The integration preserves available source/licence metadata; users and developers remain responsible for the rights/terms applicable to each item and use case.

### “Official”

Reserve **official** for an upstream party's own documentation/API when that is what is meant.

For Melodex-maintained integrations, prefer **project-maintained reference integration**.

## Repository versus installed application

Use these distinctions:

- **the repository includes** — source/package exists in the Git repository;
- **built into the desktop app** — available as part of the application runtime;
- **available in the Plugin Directory** — discoverable/installable through the registry;
- **ships in a tagged release** — actually included in that release artifact.

Do not use “ships with Melodex” when the intended meaning is only “exists in the repository”.

## If a claim is hard to label

State the observable fact instead.

For example:

```text
Bad:  secure plugin installation
Good: package size/SHA-256 and package ID/version are checked against registry metadata

Bad:  official provider
Good: project-maintained reference provider

Bad:  stable MPP API
Good: MPP 1.0 preview compatibility target

Bad:  verified plugin
Good: registry-verified package
```

Precise language is part of the product's trust model.

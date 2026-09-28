# Installing Third-party Providers and Extensions

Desktop Melodex supports two extension package types:

```text
.mdxprovider   catalog / playback providers
.mdxplugin     identity / metadata / artwork / lyrics
```

## Preferred public/community path — Plugin Directory

Open:

```text
Sources
→ Explore plugins…
```

The directory shows registry metadata before install, including:

- stable ID;
- publisher;
- version;
- licence;
- registry status;
- capabilities;
- declared permissions;
- compatibility;
- source repository;
- source-policy link;
- package SHA-256 and byte size.

Registry installs download over HTTPS and must match the registry size/SHA-256 before installation.

For new installs, Melodex records installation provenance so it can distinguish a registry-verified package from a manual local package.

## Local development / manual install

Enable **Show power tools** in Sources, then choose:

```text
Install .mdxprovider…
```

or:

```text
Install .mdxplugin…
```

Manual installation is useful while developing your own extension.

Current limitation: the manual-file path does **not** provide the same registry review/provenance context as the Plugin Directory.

Melodex records the local package hash for new manual installs, but there is no registry digest/publisher record to verify it against.

Only install a manual package you trust.

## Process isolation

Third-party desktop providers/extensions run outside the Melodex GUI process.

That improves failure isolation, but it is **not a complete OS sandbox**.

The process still has the operating-system permissions of the current user unless your OS/container adds stronger restrictions.

Declared network/filesystem permissions should be treated as transparency/review metadata today, not universal kernel-level enforcement.

See:

- [Status, stability and trust](developers/00_STATUS_AND_STABILITY.md)
- [Permissions and security](developers/07_PERMISSIONS_SECURITY.md)
- [Plugin Directory](PLUGIN_DIRECTORY.md)

# Tutorial — Publish a Community Plugin

Melodex's plugin ecosystem is designed to be decentralized. Your extension can live in its own repository; the Melodex registry can act as an index.

## 1. Prepare the project

Include:

```text
README.md
LICENSE
SOURCE_POLICY.md
tests / fixtures
manifest.json or capabilities.json
```

## 2. Use a stable ID

Prefer reverse-domain style:

```text
org.example.my-provider
com.example.artwork
```

## 3. Document capabilities and permissions

State exactly what the extension contributes and what access it needs.

## 4. Document source policy

Answer:

- What source/API is used?
- What permits the integration?
- Authentication?
- Rate limit?
- Caching?
- Offline/download?
- Commercial restrictions?
- Attribution?
- Per-item rights?

## 5. Run tests

For MPP providers:

```bash
melodex-provider validate .
melodex-provider doctor .
melodex-provider pack .
```

For capability extensions:

```bash
melodex-extension validate .
melodex-extension doctor .
melodex-extension pack .
```

Also run your own fixture tests. Publish the resulting `.mdxprovider` or `.mdxplugin` from your own repository/release page.

## 6. Registry metadata

A registry record should identify:

```text
id
name
version
kind
status
capabilities
licence
source repository
distribution URL
compatibility
permissions
source policy
```

Initial third-party entries can be `community`; reviewed entries may later become `reviewed`.

Review means the plugin was checked against project requirements. It is not a guarantee of upstream availability or every returned item's rights status.

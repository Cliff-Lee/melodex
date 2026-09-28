# Support

Before filing an issue, check:

- [Start Here](docs/START_HERE.md)
- [FAQ](docs/FAQ.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Plugin Directory](docs/PLUGIN_DIRECTORY.md) for provider/extension installation questions

## A useful bug report

Include:

- operating system and Melodex version;
- whether you installed a tagged release or are running current `main`;
- whether the source is Local Files, Jamendo, User Streams or a third-party provider;
- provider/extension name and version when relevant;
- the smallest reproducible steps;
- what you expected and what happened instead.

## Export redacted diagnostics

For source/plugin problems in the desktop app:

```text
Sources
→ Show power tools
→ Export diagnostics…
```

The JSON export is designed to include useful runtime and installation facts while omitting plugin configuration values, API keys/tokens, local-library paths, user-stream URLs, playback URLs, request headers and cookies.

It may include system/version information, plugin IDs, declared permissions, configuration **status** (not values), redacted extension health categories, public source-repository URLs and package SHA-256 values.

Review the file yourself before attaching it to a public issue.

## Do not post secrets

Never paste provider passwords, API keys, OAuth/session tokens, Bridge tokens, MCP tokens, cookies, private signed media URLs or other credentials into a public issue.

If you discover a security vulnerability, follow [SECURITY.md](SECURITY.md) instead of opening a public exploit report.

## Contributor questions

If you want to help but do not know where to begin, use [Your First Melodex Contribution](docs/FIRST_CONTRIBUTION.md) or choose **Community / newcomer question** in the GitHub issue chooser.

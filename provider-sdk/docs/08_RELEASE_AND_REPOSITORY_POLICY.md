# 8. Clean release and provider repository policy

## 8.1 Public Melodex repository

Should contain:

- Melodex Core;
- provider protocol/specification;
- Local Files provider;
- demonstrably authorized/open providers chosen by the project;
- Provider Bridge;
- SDK and examples;
- Flow/LLM/taste systems.

Should not contain source-specific bypass or circumvention code.

## 8.2 Provider directory

If Melodex later operates an official provider directory, inclusion should require:

- publisher identity;
- source repository;
- declared domains and permissions;
- licence;
- privacy statement when credentials/analytics are involved;
- confirmation that the provider author has a lawful basis to integrate the source;
- no DRM/access-control circumvention;
- no hidden network destinations.

The directory can still allow users to install an arbitrary file manually in desktop Power mode without implying endorsement.

## 8.3 Manual provider installation

The UI should make provenance explicit:

> This provider was installed from a file and is not reviewed by Melodex.

The user must confirm requested permissions.

## 8.4 Diagnostic export

A provider diagnostic bundle should include:

- manifest;
- Melodex/provider versions;
- capability list;
- redacted request/error logs;
- health check results.

It must exclude:

- bearer tokens;
- cookies;
- passwords;
- playback signed URLs;
- listening-history content unless the user opts in.

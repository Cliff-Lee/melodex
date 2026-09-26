# Implementation checklist

This repository covers the public protocol/SDK layer. Checkmarks below indicate what is already present here, not what has already landed in the Melodex application.

## Milestone A — provider-neutral desktop core

- [x] Define normalized provider models.
- [ ] Add `ProviderManager` to Melodex Core.
- [ ] Implement `LocalFilesProvider` through the same interface.
- [ ] Refactor `StreamBridge` to generic `PlaybackBridge`.
- [ ] Change `MelodexPlayer` to accept `ProviderManager`.
- [ ] Convert AI playlist resolution to global `CatalogResolver`.
- [ ] Add source badges/status to UI only where necessary.

## Milestone B — desktop SDK

- [x] Manifest schema and validation CLI.
- [x] `.mdxprovider` package format and pack command.
- [ ] `.mdxprovider` installer in Melodex.
- [ ] Out-of-process provider transport reference host.
- [ ] Permissions/trust sheet in Melodex.
- [ ] Provider logs and health screen.
- [x] SDK `init` / `validate` / `pack` commands.
- [ ] SDK conformance `test` command.

## Milestone C — Provider Bridge

- [x] Define HTTPS/OpenAPI mapping.
- [ ] Reference Provider Bridge server.
- [ ] Device pairing / QR flow.
- [ ] Token revocation.
- [ ] Docker packaging.
- [ ] LAN discovery as opt-in.

## Milestone D — mobile

- [x] Define Android/iOS architecture.
- [ ] Android client to Provider Bridge.
- [ ] Android scoped local-file provider.
- [ ] iOS client to Provider Bridge.
- [ ] iOS Files/iCloud local provider.
- [ ] Shared queue/taste sync design (optional and separate from provider credentials).

## Milestone E — clean public release

- [x] Publish Provider SDK docs and fictional demo provider.
- [x] Add public source-neutrality/repository policy.
- [x] Add release-safety string/secret guardrail script.
- [ ] Remove source-specific code from Melodex Core before publishing the app repository.
- [ ] Review all app dependencies and licences.
- [ ] Sign/notarize desktop builds.
- [ ] Publish only reviewed providers in any official directory.

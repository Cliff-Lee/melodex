# 3. Platform Matrix

> **Architecture-target note:** this matrix describes the intended cross-platform provider model, not a promise that every listed client/build is currently shipped. The public repository currently includes the desktop app and Android Bridge-client path; iOS remains design/planned work.


## 3.1 Recommended support model

| Capability | macOS | Windows | Linux | Android | iOS |
|---|---|---|---|---|---|
| Built-in/provider architecture target | Yes | Yes | Yes | Yes | Planned |
| Local folders | Yes | Yes | Yes | Scoped storage | Files/iCloud scope |
| Install executable provider bundle | Desktop-supported | Desktop-supported | Source/desktop target | No in store build | No |
| Connect Provider Bridge | Yes | Yes | Yes | Yes | Yes |
| Provider development mode | Yes | Yes | Yes | Via Bridge | Planned via Bridge |
| OS credential vault | Keychain | Credential Manager | Secret Service/KWallet | Keystore | Keychain |
| Background audio | Yes | Yes | Yes | MediaSession | AVAudioSession |

## 3.2 macOS

- `.mdxprovider` bundles may contain a universal arm64/x86_64 executable or a Python provider launched with Melodex's isolated provider runtime.
- Provider processes live under `~/Library/Application Support/Melodex/Providers/`.
- Secrets live in Keychain.
- Public releases should sign/notarize Melodex; third-party provider signatures are shown separately.

## 3.3 Windows

- Provider executable can be `.exe` or a packaged Python worker.
- Install path: `%APPDATA%\\Melodex\\Providers`.
- Secrets use Windows Credential Manager / DPAPI-backed storage.
- Windows Defender reputation means provider signing should be encouraged.

## 3.4 Linux

- Native executable, Python worker, or container-backed provider.
- Install path: `${XDG_DATA_HOME:-~/.local/share}/melodex/providers`.
- Secrets use Secret Service when available; encrypted fallback only with explicit warning.
- Flatpak builds should prefer Provider Bridge for externally installed connectors unless portals/permissions are configured.

## 3.5 Android

For the public Play Store build, do **not** execute arbitrary downloaded provider code.

Supported extension paths:

1. built-in provider compiled into the app;
2. Provider Bridge over HTTPS;
3. Android Storage Access Framework for user-owned files.

A side-loaded developer build may experiment with additional mechanisms, but it should not define the public architecture.

## 3.6 iOS

Downloaded executable plugins are not an appropriate architecture for the App Store build.

Use:

1. built-in providers;
2. Provider Bridge;
3. Files/iCloud/document-provider access for user-owned media.

This is why the Bridge is part of v1 rather than a future add-on.

## 3.7 One configuration across the house

The Provider Bridge can become the ideal cross-platform model:

```text
Home server / desktop
  ├─ personal library provider
  ├─ Navidrome provider
  ├─ Jellyfin provider
  └─ other user-installed providers
          │
          ├── Mac Melodex
          ├── Windows Melodex
          ├── Android Melodex
          └── iPhone/iPad Melodex
```

A provider is configured once; credentials never have to be copied manually to every client.

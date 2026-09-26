# Install on Android

Download the APK from GitHub Releases, or install the Play Store build when available.

Android intentionally does **not** execute downloaded provider code. It connects to providers through a Melodex Provider Bridge running on a desktop, NAS or home server.

## Connect

1. Open desktop Melodex.
2. Go to **Sources → Provider Bridge**.
3. Choose LAN access.
4. Copy the bridge URL and bearer token.
5. Enter both in Android Melodex and tap **Connect**.

Your phone can now search and play sources exposed by that Bridge.

### Security

Treat the bearer token like a password. Use the bridge only on networks you trust. For access outside your home LAN, put the Bridge behind HTTPS/VPN rather than exposing the raw port to the internet.

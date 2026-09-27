# Install Melodex on Linux

The v0.2 release provides an **x86_64 AppImage**.

## Download

From the latest GitHub Release, download:

`Melodex-Linux-x86_64.AppImage`

## Make it executable

```bash
chmod +x Melodex-Linux-x86_64.AppImage
```

## Run

```bash
./Melodex-Linux-x86_64.AppImage
```

No system-wide installation is required.

## Add music

1. Open **Sources**.
2. Choose **Add local folder...**.
3. Select a music folder.
4. Open **My music** and test playback.

## Optional sources

- **User Streams** is built in.
- **Jamendo** requires your own developer client ID.
- **Internet Archive** is an official optional `.mdxprovider`.
- Third-party providers can be installed through **Show power tools**.

## Local application data

Melodex uses `$XDG_DATA_HOME/melodex`, or `~/.local/share/melodex` when `XDG_DATA_HOME` is not set.

## If the AppImage will not start

Run it from a terminal to see the error output and confirm the file is executable.

See [Troubleshooting](TROUBLESHOOTING.md).

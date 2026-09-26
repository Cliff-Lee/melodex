# 2. Source UX — simple by default, deep on demand

## 2.1 First run

The first-run question should be:

> **Where is your music?**

Large choices:

- **This computer**
- **Home server / NAS**
- **Music service**
- **Melodex Bridge**
- **I'll do this later**

Do not use the words *provider*, *plugin*, *endpoint*, *manifest* or *API* in the beginner path.

## 2.2 Sources screen

```text
SOURCES

This computer                         ✓ Connected
Home Navidrome                        ✓ Connected
Living-room Melodex Bridge            ✓ Connected

                         + Add source
```

Selecting a source shows only:

- status;
- account/server name;
- music count if available;
- offline availability;
- Disconnect.

A `•••` menu exposes expert controls.

## 2.3 Add Source sheet

### Simple mode

```text
Add music source

[ This computer ]
[ Home server / NAS ]
[ Connect a service ]
[ Melodex Bridge ]
```

### Power mode adds

```text
[ Install provider file… ]
[ Connect provider URL… ]
[ Developer tools… ]
```

## 2.4 Installing a desktop provider

Double-clicking a `.mdxprovider` file opens a trust sheet:

```text
Add “Example Provider”?

Publisher: Example Org
Version: 1.2.0

This provider requests:
✓ Network access to api.example.org
✓ Playback access
○ Offline downloads

It cannot access:
— your Melodex taste history
— other providers' credentials
— arbitrary files
— LLM keys

[Cancel]                         [Add Source]
```

Permissions are derived from the manifest. Domain access outside declared hosts is denied by default where technically enforceable and visibly warned otherwise.

## 2.5 Bridge pairing

Desktop/server displays:

```text
Connect another Melodex device

[ QR CODE ]

Expires in 4:58
```

Mobile scans it and receives:

- bridge URL;
- one-time pairing secret;
- server fingerprint.

The long-lived token is stored in the platform credential vault.

## 2.6 Failure UX

Errors should be action-oriented:

Bad:

> Provider playback.resolve failed: 401

Good:

> **Home Server needs you to sign in again.**
> Your other music sources still work.
> [Sign in]

Bad:

> subprocess exited 1

Good:

> **Example Provider stopped unexpectedly.**
> Melodex disabled it for this session.
> [Restart] [Details]

## 2.7 Source selection during search

Default search is global. Results carry subtle source badges only when useful.

If the same recording exists in several sources, Melodex should show one result and choose playback using this preference order:

1. permanent local file;
2. available offline copy;
3. user's preferred source;
4. highest-quality playable source;
5. fastest healthy source.

Power mode can expose `Play using…`.

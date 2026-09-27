# FAQ

## Does Melodex need an LLM?
No. Playback, Flow, Play for Me, taste memory, Moments and local sources work without one.

## Does Melodex include a music subscription?
No. Melodex plays music from sources you connect.

## What sources are built in?
**This computer** and **User Streams** are built in. Jamendo is the reference provider and requires your own developer client ID. Internet Archive is an official optional `.mdxprovider` for publicly accessible Archive audio.

## Can I add my own provider?
Yes on desktop through MPP v1 `.mdxprovider` packages. See the Provider SDK.

## Why can Internet Archive take a few seconds to start?
The provider may need to resolve an Archive item to a playable file and route it through the local Playback Gateway. Very large aggregate media files can take longer than ordinary tracks.

## Why does Android use a Bridge?
Android intentionally avoids executing arbitrary downloaded provider code. The Bridge runs providers on a computer/NAS and exposes a narrow authenticated API to the phone.

## Is my listening history uploaded?
Not by default. It stays local unless you explicitly submit relevant context to a configured external LLM.

## Can provider credentials leak into AI context?
Melodex strips playback-only fields such as headers, cookies, refresh tokens, signed stream URLs and local file paths from LLM/control status responses.

## Why is Flow better with FFmpeg available?
Deep local audio analysis can use FFmpeg decoding. Without it, Flow degrades gracefully rather than inventing analysis.

## Where are the full manuals?
- [User Manual v0.2](manuals/Melodex_User_Manual_v0.2.pdf)
- [Power User Manual v0.2](manuals/Melodex_Power_User_Manual_v0.2.pdf)

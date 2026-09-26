# FAQ

## Does Melodex need an LLM?
No. Flow, Play for Me, taste memory and local playback work without one.

## Does Melodex include a music subscription?
No. Melodex plays music from sources you connect.

## What sources ship with it?
Local Files and the Jamendo reference provider. Jamendo requires your own developer client ID.

## Can I add my own provider?
Yes on desktop through MPP v1 `.mdxprovider` packages. See the Provider SDK.

## Why does Android use a Bridge?
Android intentionally avoids executing arbitrary downloaded provider code. The Bridge runs providers on a computer/NAS and exposes a narrow authenticated API to the phone.

## Is my listening history uploaded?
No, unless you explicitly send relevant context to a configured external LLM as part of a prompt.

## Why is Flow better with FFmpeg installed?
FFmpeg lets Melodex decode local audio for BPM/key/energy/structure analysis. Without it, Flow degrades gracefully.

## Can I use Melodex with any third-party website?
Only if a compatible provider exists and your use of that provider complies with the source's terms and applicable law.

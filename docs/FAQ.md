# FAQ

## Does Melodex need an LLM?
No. Flow, Play for Me, taste memory and local playback work without one.

## Does Melodex include a music subscription?
No. Melodex plays music from sources you connect.

## What sources ship with it?
The desktop app has built-in **Local Files**, **User Streams**, and the **Jamendo reference provider**. Jamendo requires your own developer client ID.

Melodex also maintains optional legal/open reference plugins, such as Radio Browser and LibriVox providers plus MusicBrainz/Wikimedia enrichment extensions. Builds that include the Plugin Directory can discover these separately; they are not the same thing as built-in Core sources.

## Can I add my own provider?
Yes on desktop through MPP `.mdxprovider` packages. MPP is implemented and usable, but its current 1.0 wire identifier remains a preview compatibility target. See the [Provider SDK](../provider-sdk/README.md).

## Why does Android use a Bridge?
Android intentionally avoids executing arbitrary downloaded provider code. The Bridge runs providers on a computer/NAS and exposes a narrow authenticated API to the phone.

## Is my listening history uploaded?
Melodex does not automatically upload your listening history to a Melodex account/service.

If you configure a remote LLM and submit an Ask Melodex prompt, the current context can include recent listening/taste information. See [Privacy](PRIVACY.md) for the exact current context and other network activity.

## Why is Flow better with FFmpeg installed?
FFmpeg lets Melodex decode local audio for BPM/key/energy/structure analysis. Without it, Flow degrades gracefully.

## Can I use Melodex with any third-party website?
Only if a compatible provider exists and your use of that provider complies with the source's terms and applicable law.

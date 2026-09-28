# LibriVox Example Provider

Current MPP example provider.

Capabilities:

```text
search
track
playback
offline
```

A LibriVox audiobook is treated as an album/project and each section/chapter is
returned as a track.

Example searches:

```text
Odyssey
Sherlock Holmes
Jane Austen
Dickens
```

The example first searches titles; if no title match is found it tries the author
field.

Because LibriVox recordings are public domain in the U.S., the example can
legitimately demonstrate `offline_allowed` playback resources.

Be considerate of the API. Do not bulk-query rapidly.

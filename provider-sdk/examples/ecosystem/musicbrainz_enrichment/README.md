# MusicBrainz Enrichment Example

Experimental extension implementing:

```text
identity.resolve
metadata.enrich
```

## Why this is a good ecosystem example

MusicBrainz is designed for music metadata and canonical identity.

The example demonstrates:

- matching weak title/artist metadata to a recording MBID;
- returning candidate confidence/evidence;
- enriching a known recording;
- field-level provenance;
- a meaningful User-Agent;
- one-request-per-second pacing.

## API policy

MusicBrainz currently documents that non-commercial web-service use is free,
no API key is required, a meaningful User-Agent is required, and the usual
IP rate is roughly one request per second.

Commercial applications should review current MetaBrainz terms.

## Offline fixture mode

```bash
MELODEX_EXAMPLE_FIXTURES=1 python plugin.py
```

## Current runtime status

This is a reference implementation of the experimental v0.1 enrichment
contracts. Current Melodex releases may not discover it automatically yet.

# Music sources

Melodex is source-neutral. A source is any provider that can search/browse music and resolve a selected track to a playable local file or stream.

## Built in

### This computer

Your own local audio files. No network access required.

### Jamendo reference provider

A real online example using the public Jamendo API. You supply your own developer client ID. Melodex keeps Jamendo attribution and licence metadata with each result.

Jamendo's API has its own terms and licence requirements; review them before publishing an application that uses it.

## Third-party providers on desktop

Use **Sources → Install `.mdxprovider`**. Melodex runs external providers out-of-process using MPP v1.

Before installing a provider, review its publisher, permissions and source code when available.

## Android

Android uses Provider Bridge rather than arbitrary downloaded provider code.

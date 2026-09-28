# Third-Party Notices

Melodex code is MIT licensed unless a subdirectory/file states otherwise.

This notice documents external software inspiration, services, datasets and media sources that Melodex can use. External music, artwork, metadata and upstream APIs are **not** relicensed under the Melodex MIT licence.

## Parachord / Tomahawk design lineage

Melodex is an independent project.

Its source-neutral/multi-source resolver design is inspired in part by Parachord and the earlier Tomahawk approach.

Parachord: https://github.com/Parachord/parachord

Parachord is MIT licensed (copyright Jason Herskowitz, 2025).

The Melodex resolver was implemented independently rather than copied wholesale from Parachord source. The notice records design lineage/transparency.

## MusicBrainz / MetaBrainz Foundation

Melodex and its reference extension can retrieve music identity/metadata from MusicBrainz.

MusicBrainz documents different licensing for different data classes, including CC0 for core database data and separate terms for supplementary data.

See: https://musicbrainz.org/doc/About/Data_License

MusicBrainz/MetaBrainz names and marks remain the property of their respective owners. Melodex is not affiliated with or endorsed by MetaBrainz.

## Cover Art Archive

Melodex can retrieve release artwork from the Cover Art Archive.

See: https://musicbrainz.org/doc/Cover_Art_Archive

Cover images can remain copyrighted by artists, labels, designers or other rightsholders. Melodex does not apply one blanket licence to all archive artwork.

## Wikidata

Melodex may use Wikidata links to connect MusicBrainz identities with Wikimedia Commons media.

Wikidata structured data is released under CC0.

See: https://www.wikidata.org/wiki/Wikidata:Licensing

## Wikimedia Commons

Melodex can use Wikimedia Commons for artist/artwork enrichment.

Commons files have per-file licensing/attribution requirements.

Current Melodex Wikimedia enrichment records, when available:

- creator/credit;
- licence name;
- licence URL;
- source/file-description URL.

Melodex does not relicense Commons media.

See: https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia

## Jamendo

Jamendo is available as a built-in reference provider. Users supply their own Jamendo developer Client ID.

Jamendo API terms require creator/Jamendo attribution and a direct backlink, and distinguish commercial API use.

Melodex preserves the returned creator attribution, track licence URL and Jamendo source-page link.

See:

- https://devportal.jamendo.com/api_terms_of_use
- https://developer.jamendo.com/

Melodex is not affiliated with or endorsed by Jamendo.

## Radio Browser

Melodex includes a Provider SDK reference package for Radio Browser.

Radio Browser is an open radio-directory/API project. Individual radio-station streams/programming remain controlled by their respective operators/rightsholders; Melodex does not claim redistribution rights over station programming.

See:

- https://api.radio-browser.info/
- https://docs.radio-browser.info/

## LibriVox

Melodex includes a Provider SDK reference package for LibriVox.

LibriVox states that its recordings are public domain in the United States and asks users in other jurisdictions to check local copyright status.

See: https://librivox.org/pages/public-domain/

## Internet Archive

The repository contains an Internet Archive provider source/reference integration.

Rights and access conditions vary by Archive item. Melodex does not treat availability on Internet Archive as one blanket copyright licence.

See: https://archive.org/developers/

## Python / application dependencies

Melodex uses third-party dependencies including:

- PySide6 / Qt for Python;
- NumPy;
- mutagen;
- requests;
- PyInstaller and Pillow for packaging/build workflows;
- the optional Python MCP SDK;
- jsonschema in the Provider SDK;
- optional Beautiful Soup in Provider SDK web integrations.

Those dependencies retain their own licences/copyright notices. Refer to each installed distribution/upstream project for the exact applicable licence/version.

## Android dependencies

The Android preview uses AndroidX/Jetpack Compose and Media3/ExoPlayer dependencies declared in `android/app/build.gradle.kts`.

Those dependencies retain their own licences and notices.

## Media/data rule

Third-party API availability, public-domain status, Creative Commons licensing, and copyright can be jurisdiction/item-specific.

Melodex attempts to preserve relevant source/licence/provenance fields, but downstream users/reusers remain responsible for complying with applicable rights and terms.

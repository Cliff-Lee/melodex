# Jamendo reference provider

The Jamendo provider exists to demonstrate a real online Melodex source without bundling a proprietary catalogue connector.

## Credentials

Melodex does not ship a shared production credential. Create your own Jamendo developer application and enter its `client_id` in **Sources → Jamendo settings**.

Jamendo states that API credentials are personal to the developer/application and should not be shared with third parties. This is why Melodex asks the user/developer to supply their own client ID rather than embedding one in the public repository.

## Content and attribution

Jamendo's API terms state that content exposed through the API is published under a Creative Commons licence, and require applications to credit the artist, credit Jamendo as the provider, and provide a direct backlink to the relevant Jamendo content page.

The reference provider therefore retains:

- artist name
- Jamendo source attribution
- the returned `shareurl`/content-page URL
- Creative Commons licence URL when returned by the API

The desktop UI exposes the source page from search results and while a Jamendo track is playing.

## Commercial use

Jamendo's published API terms say the API may be used freely for non-commercial uses and instruct developers to contact Jamendo for commercial uses. Review the current terms before distributing a commercial build.

## Downloading / caching

The reference provider is intentionally a streaming example and declares no offline-download capability. Jamendo's API documentation also exposes `audiodownload_allowed` for tracks, while its terms restrict applications specifically designed around persistent caching/offline access.

If you extend this provider, comply with the current API terms and each track's licence rather than assuming every operation is permitted.

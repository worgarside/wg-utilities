# Spotify Flat Files

These files are all real responses from the [Spotify API](https://developer.spotify.com/documentation/web-api/reference/).
The directory is structured so that each file is at the same path that the original response was retrieved from (again with anonymisation where applicable).

## Modifications

The following modifications have been made to the original responses:
1. I have removed all market data from the JSON responses: it was bloating the files by a considerable amount and it's never used.
2. I have anonymised the JSON responses, mainly by removing my email, user ID, and any other unique identifiers/PII.
3. The file at `tests/flat_files/json/spotify/me/tracks/offset=200&limit=50.json` has had the value for `$.next` set to `null`, otherwise I'd need an extra 155 files to complete the full set of responses.
4. The file at `tests/flat_files/json/spotify/search/query=uncommon+search&type=track&offset=150&limit=50.json` is a real search response; I don't know why that URL is specified as a `next` value when there aren't any results.

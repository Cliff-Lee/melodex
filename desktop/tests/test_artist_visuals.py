from pathlib import Path

from melodex.metadata import RichMetadataService


def test_artist_photo_from_wikidata_link(tmp_path: Path):
    svc = RichMetadataService(tmp_path / 'data')
    svc._download_artwork = lambda url: tmp_path / 'artist.jpg'
    (tmp_path / 'artist.jpg').write_bytes(b'jpg')
    svc._remote_json = lambda key, url, max_age=0: {
        'entities': {
            'Q42': {
                'labels': {'en': {'value': 'Artist Example'}},
                'claims': {
                    'P18': [
                        {'mainsnak': {'datavalue': {'value': 'Artist Example Portrait.jpg'}}}
                    ]
                },
            }
        }
    }
    artist = {'name': 'Artist Example', 'links': [{'type': 'wikidata', 'url': 'https://www.wikidata.org/wiki/Q42'}]}
    out = svc.artist_photo(artist)
    assert out['source'] == 'Wikimedia Commons'
    assert out['wikidata_qid'] == 'Q42'
    assert out['path'].endswith('artist.jpg')
    assert 'Wikimedia Commons image' in out['attribution']


def test_discography_parsing_and_sorting(tmp_path: Path):
    svc = RichMetadataService(tmp_path / 'data')
    svc._download_artwork = lambda url: None
    svc._mb_json = lambda *args, **kwargs: {
        'release-groups': [
            {'id': 'rg2', 'title': 'Beta', 'primary-type': 'Album', 'first-release-date': '2004-03-02'},
            {'id': 'rg1', 'title': 'Alpha', 'primary-type': 'EP', 'first-release-date': '1999-07-01'},
        ]
    }
    rows = svc.discography('artist-1')
    assert [row['id'] for row in rows] == ['rg1', 'rg2']
    assert rows[0]['year'] == 1999
    assert rows[1]['primary_type'] == 'Album'


def test_enrich_includes_visual_fields(tmp_path: Path):
    svc = RichMetadataService(tmp_path / 'data')
    svc.local_lyrics = lambda track: {'text': '', 'synced': [], 'source': ''}
    class DummyIdentity:
        artist_mbid = 'artist-1'
        recording_mbid = 'rec-1'
        release_group_mbid = ''
        release_mbid = ''
        def as_dict(self):
            return {'artist_mbid': 'artist-1', 'recording_mbid': 'rec-1'}
    svc.identify = lambda track: DummyIdentity()
    svc.artist_info = lambda mbid: {'name': 'Example', 'links': [{'type': 'wikidata', 'url': 'https://www.wikidata.org/wiki/Q42'}]}
    svc.artist_photo = lambda artist: {'source': 'Wikimedia Commons', 'path': '/tmp/artist.jpg'}
    svc.discography = lambda mbid: [{'id': 'rg1', 'title': 'Alpha'}]
    svc.recording_credits = lambda mbid: []
    svc.artwork = lambda track, identity: {'source': 'Cover Art Archive', 'path': '/tmp/cover.jpg'}
    out = svc.enrich({'artist': 'A', 'title': 'B'})
    assert out['artist_photo']['source'] == 'Wikimedia Commons'
    assert out['discography'][0]['id'] == 'rg1'

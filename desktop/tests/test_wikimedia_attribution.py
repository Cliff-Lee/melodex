from pathlib import Path

from melodex.metadata import RichMetadataService


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload
    def raise_for_status(self):
        return None
    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.headers = {}
        self.calls = []
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.payload)
    def close(self):
        pass


def commons_payload():
    return {
        "query": {
            "pages": [{
                "title": "File:Example.jpg",
                "imageinfo": [{
                    "url": "https://upload.wikimedia.org/example-original.jpg",
                    "thumburl": "https://upload.wikimedia.org/example-640.jpg",
                    "descriptionurl": "https://commons.wikimedia.org/wiki/File:Example.jpg",
                    "extmetadata": {
                        "Artist": {"value": '<a href="/wiki/User:Jane">Jane Doe</a>'},
                        "Credit": {"value": "Own work"},
                        "LicenseShortName": {"value": "CC BY-SA 4.0"},
                        "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0/"},
                        "AttributionRequired": {"value": "true"},
                        "Copyrighted": {"value": "True"},
                    },
                }],
            }]
        }
    }


def test_commons_file_info_captures_file_level_credit_and_license(tmp_path: Path):
    session = FakeSession(commons_payload())
    svc = RichMetadataService(tmp_path / "data", session=session)
    info = svc._commons_file_info("Example.jpg")
    assert info["creator"] == "Jane Doe"
    assert info["license_name"] == "CC BY-SA 4.0"
    assert info["license_url"].endswith("/by-sa/4.0/")
    assert info["description_url"].endswith("File:Example.jpg")
    assert info["image_url"].endswith("example-640.jpg")
    assert info["attribution_required"] == "true"


def test_credit_line_prefers_explicit_attribution():
    line = RichMetadataService._commons_credit_line({
        "explicit_attribution": "Jane Doe / Example Foundation / CC BY 4.0",
        "creator": "Ignored",
        "license_name": "CC BY 4.0",
    })
    assert line == "Jane Doe / Example Foundation / CC BY 4.0"


def test_credit_line_uses_creator_commons_and_license():
    line = RichMetadataService._commons_credit_line({
        "creator": "Jane Doe",
        "credit": "Own work",
        "license_name": "CC BY-SA 4.0",
    })
    assert line == "Jane Doe / Wikimedia Commons / CC BY-SA 4.0"


def test_artist_photo_returns_attribution_metadata(tmp_path: Path):
    svc = RichMetadataService(tmp_path / "data")
    svc._remote_json = lambda *args, **kwargs: {
        "entities": {"Q1": {"claims": {"P18": [{"mainsnak": {"datavalue": {"value": "Example.jpg"}}}]}}}
    }
    svc._extract_wikidata_qid = lambda artist: "Q1"
    svc._commons_file_info = lambda name: {
        "image_url": "https://upload.wikimedia.org/example.jpg",
        "description_url": "https://commons.wikimedia.org/wiki/File:Example.jpg",
        "creator": "Jane Doe",
        "credit": "Own work",
        "license_name": "CC BY-SA 4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "attribution_required": "true",
        "copyrighted": "True",
        "explicit_attribution": "",
    }
    out_path = tmp_path / "artist.jpg"
    out_path.write_bytes(b"jpg")
    svc._download_artwork = lambda url: out_path
    out = svc.artist_photo({"name": "Example"})
    assert out["creator"] == "Jane Doe"
    assert out["license_name"] == "CC BY-SA 4.0"
    assert out["description_url"].endswith("File:Example.jpg")
    assert out["attribution"] == "Jane Doe / Wikimedia Commons / CC BY-SA 4.0"

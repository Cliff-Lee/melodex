"""Reference helpers for Melodex Provider Protocol preview."""

from .models import Album, Artist, PlaybackResource, ProviderError, Track
from .validation import ManifestValidationError, load_manifest, validate_manifest
from .web import WebResponse, WebSession, absolute_url, extract_first, first_of, opaque_id

__all__ = [
    "Album",
    "Artist",
    "Track",
    "PlaybackResource",
    "ProviderError",
    "ManifestValidationError",
    "load_manifest",
    "validate_manifest",
    "WebResponse",
    "WebSession",
    "absolute_url",
    "extract_first",
    "first_of",
    "opaque_id",
]

__version__ = "0.7.0"

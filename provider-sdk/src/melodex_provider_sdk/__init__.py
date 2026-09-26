"""Reference helpers for Melodex Provider Protocol preview."""

from .models import Album, Artist, PlaybackResource, ProviderError, Track
from .validation import ManifestValidationError, load_manifest, validate_manifest

__all__ = [
    "Album",
    "Artist",
    "Track",
    "PlaybackResource",
    "ProviderError",
    "ManifestValidationError",
    "load_manifest",
    "validate_manifest",
]

__version__ = "0.1.0"

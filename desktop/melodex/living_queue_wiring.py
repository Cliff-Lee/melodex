"""Connect the Living Queue controls to playback and Journey Live."""

from __future__ import annotations

from typing import Any


def connect_living_queue(
    player: Any, playback_feature: Any, journey_workspace: Any
) -> None:
    """Wire queue editing, route steering, and explanations across owners."""
    playback_feature.removeQueueItemRequested.connect(
        lambda index: player.remove_queue_item(int(index))
    )
    playback_feature.moveQueueItemRequested.connect(
        lambda source, target: player.move_queue_item(int(source), int(target))
    )
    playback_feature.replaceUpcomingRequested.connect(
        lambda tracks: player.replace_upcoming(list(tracks or []))
    )
    playback_feature.moreLikeRequested.connect(journey_workspace.request_more_like)
    playback_feature.towardArtistRequested.connect(
        journey_workspace.request_toward_artist
    )
    playback_feature.towardRegionRequested.connect(
        journey_workspace.request_toward_region
    )
    journey_workspace.protectQueueTrackRequested.connect(
        playback_feature.keep_queue_track
    )
    playback_feature.steerJourneyRequested.connect(
        journey_workspace.request_live_steer
    )
    journey_workspace.replaceUpcomingRequested.connect(
        playback_feature.apply_journey_replan
    )
    journey_workspace.queueTrackReasonsRequested.connect(
        playback_feature.set_queue_track_reasons
    )

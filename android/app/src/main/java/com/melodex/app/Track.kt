package com.melodex.app

import android.net.Uri

/** A playable item from either this phone or a connected Melodex Bridge. */
data class Track(
    val id: String,
    val title: String,
    val artist: String,
    val album: String = "",
    val uri: Uri,
    val artworkUri: Uri? = null,
    val durationMs: Long = 0L,
    val source: Source = Source.LOCAL,
    val providerId: String = "",
    val remoteTrackId: String = "",
) {
    enum class Source { LOCAL, BRIDGE }
}

package com.melodex.app

import android.content.ContentResolver
import android.content.ContentUris
import android.content.Context
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.MediaStore

internal const val LOCAL_AUDIO_PREVIEW_SIZE = 40

/** Reads audio items Android has indexed, without scanning paths or copying files. */
internal fun queryLocalAudioTracks(
    resolver: ContentResolver,
    context: Context,
    limitPerVolume: Int? = null
): List<Track> {
    val volumes = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
        MediaStore.getExternalVolumeNames(context)
    } else {
        setOf(MediaStore.VOLUME_EXTERNAL)
    }
    val projection = arrayOf(
        MediaStore.Audio.Media._ID,
        MediaStore.Audio.Media.TITLE,
        MediaStore.Audio.Media.ARTIST,
        MediaStore.Audio.Media.ALBUM,
        MediaStore.Audio.Media.ALBUM_ID,
        MediaStore.Audio.Media.DURATION
    )
    val tracks = mutableListOf<Track>()

    volumes.forEach { volumeName ->
        val collection = MediaStore.Audio.Media.getContentUri(volumeName)
        val queryArgs = Bundle().apply {
            putStringArray(
                ContentResolver.QUERY_ARG_SORT_COLUMNS,
                arrayOf(MediaStore.Audio.Media.TITLE)
            )
            putInt(
                ContentResolver.QUERY_ARG_SORT_DIRECTION,
                ContentResolver.QUERY_SORT_DIRECTION_ASCENDING
            )
            if (limitPerVolume != null) {
                putInt(ContentResolver.QUERY_ARG_LIMIT, limitPerVolume)
            }
        }
        resolver.query(collection, projection, queryArgs, null)?.use { cursor ->
            val idColumn = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media._ID)
            val titleColumn = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media.TITLE)
            val artistColumn = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media.ARTIST)
            val albumColumn = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media.ALBUM)
            val albumIdColumn = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media.ALBUM_ID)
            val durationColumn = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media.DURATION)

            while (cursor.moveToNext()) {
                val id = cursor.getLong(idColumn)
                val uri = ContentUris.withAppendedId(collection, id)
                val albumId = cursor.getLong(albumIdColumn)
                val artworkUri = if (albumId > 0L) {
                    ContentUris.withAppendedId(
                        Uri.parse("content://media/external/audio/albumart"),
                        albumId
                    ).toString()
                } else {
                    ""
                }
                tracks += Track(
                    providerId = "local",
                    trackId = uri.toString(),
                    title = cleanAudioMetadata(cursor.getString(titleColumn), "Unknown track"),
                    artist = cleanAudioMetadata(cursor.getString(artistColumn), "Unknown artist"),
                    album = cleanAudioMetadata(cursor.getString(albumColumn), ""),
                    streamUrl = uri.toString(),
                    artworkUri = artworkUri,
                    durationMs = cursor.getLong(durationColumn).coerceAtLeast(0L)
                )
            }
        }
    }

    return tracks
        .distinctBy(Track::trackId)
        .sortedWith(compareBy(String.CASE_INSENSITIVE_ORDER) { it.title }.thenBy { it.artist })
}

private fun cleanAudioMetadata(value: String?, fallback: String): String =
    value?.trim()?.takeIf { it.isNotEmpty() && !it.equals("<unknown>", ignoreCase = true) } ?: fallback

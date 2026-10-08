package com.melodex.app

import android.content.ContentResolver
import android.content.ContentUris
import android.content.Context
import android.net.Uri
import android.os.Build
import android.provider.MediaStore

/** Reads audio items Android has indexed, without scanning paths or copying files. */
internal fun queryLocalAudioTracks(resolver: ContentResolver, context: Context): List<Track> {
    val collections: List<Uri> = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
        MediaStore.getExternalVolumeNames(context).map { volumeName ->
            MediaStore.Audio.Media.getContentUri(volumeName)
        }
    } else {
        listOf(MediaStore.Audio.Media.EXTERNAL_CONTENT_URI)
    }
    val projection = arrayOf(
        MediaStore.Audio.Media._ID,
        MediaStore.Audio.Media.TITLE,
        MediaStore.Audio.Media.ARTIST,
        MediaStore.Audio.Media.ALBUM
    )
    val tracks = mutableListOf<Track>()

    collections.forEach { collection ->
        resolver.query(
            collection,
            projection,
            null,
            null,
            "${MediaStore.Audio.Media.TITLE} COLLATE NOCASE ASC"
        )?.use { cursor ->
            val idColumn = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media._ID)
            val titleColumn = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media.TITLE)
            val artistColumn = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media.ARTIST)
            val albumColumn = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media.ALBUM)

            while (cursor.moveToNext()) {
                val id = cursor.getLong(idColumn)
                val uri = ContentUris.withAppendedId(collection, id)
                tracks += Track(
                    providerId = "local",
                    trackId = uri.toString(),
                    title = cursor.getString(titleColumn)?.takeIf(String::isNotBlank) ?: "Unknown track",
                    artist = cursor.getString(artistColumn)?.takeIf(String::isNotBlank) ?: "Unknown artist",
                    album = cursor.getString(albumColumn).orEmpty(),
                    streamUrl = uri.toString()
                )
            }
        }
    }

    return tracks.sortedWith(compareBy(String.CASE_INSENSITIVE_ORDER) { it.title })
}

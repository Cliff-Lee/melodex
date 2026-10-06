package com.melodex.app

import android.content.ContentUris
import android.content.Context
import android.provider.MediaStore

object LocalLibrary {
    fun read(context: Context): List<Track> {
        val resolver = context.contentResolver
        val collection = MediaStore.Audio.Media.EXTERNAL_CONTENT_URI
        val projection = arrayOf(
            MediaStore.Audio.Media._ID,
            MediaStore.Audio.Media.TITLE,
            MediaStore.Audio.Media.ARTIST,
            MediaStore.Audio.Media.ALBUM,
            MediaStore.Audio.Media.ALBUM_ID,
            MediaStore.Audio.Media.DURATION,
        )
        val tracks = mutableListOf<Track>()
        resolver.query(
            collection,
            projection,
            "${MediaStore.Audio.Media.IS_MUSIC} != 0",
            null,
            "${MediaStore.Audio.Media.TITLE} COLLATE NOCASE ASC",
        )?.use { cursor ->
            val idColumn = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media._ID)
            val titleColumn = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media.TITLE)
            val artistColumn = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media.ARTIST)
            val albumColumn = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media.ALBUM)
            val albumIdColumn = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media.ALBUM_ID)
            val durationColumn = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media.DURATION)
            while (cursor.moveToNext()) {
                val id = cursor.getLong(idColumn)
                val albumId = cursor.getLong(albumIdColumn)
                val uri = ContentUris.withAppendedId(collection, id)
                val art = if (albumId > 0L) {
                    ContentUris.withAppendedId(MediaStore.Audio.Albums.EXTERNAL_CONTENT_URI, albumId)
                        .let { android.net.Uri.withAppendedPath(it, "art") }
                } else null
                tracks += Track(
                    id = "local:$id",
                    title = cursor.getString(titleColumn)?.takeIf(String::isNotBlank) ?: "Unknown track",
                    artist = cursor.getString(artistColumn)?.takeIf(String::isNotBlank) ?: "Unknown artist",
                    album = cursor.getString(albumColumn).orEmpty(),
                    uri = uri,
                    artworkUri = art,
                    durationMs = cursor.getLong(durationColumn),
                )
            }
        }
        return tracks
    }
}

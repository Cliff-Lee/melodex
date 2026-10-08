package com.melodex.app

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import androidx.media3.common.Player
import java.util.concurrent.Executors

internal data class SavedPhoneQueue(
    val tracks: List<Track>,
    val currentIndex: Int,
    val currentPositionMs: Long,
)

/** Persists stable phone and Bridge queue identities; Bridge stream URLs are always transient. */
internal object LocalQueueStore {
    private const val DATABASE = "local_playback_queue.db"
    private const val TABLE = "queue_items"
    private const val PREFERENCES = "local_playback_queue"
    private const val INDEX_KEY = "current_index"
    private const val POSITION_KEY = "position_ms"

    private val writer = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "MelodexQueueWriter").apply { isDaemon = true }
    }

    private class QueueDatabase(context: Context) :
        SQLiteOpenHelper(context, DATABASE, null, 2) {
        override fun onCreate(db: SQLiteDatabase) {
            db.execSQL(
                """CREATE TABLE $TABLE (
                    position INTEGER PRIMARY KEY NOT NULL,
                    source TEXT NOT NULL,
                    provider_id TEXT NOT NULL,
                    track_id TEXT NOT NULL,
                    uri TEXT NOT NULL,
                    title TEXT NOT NULL,
                    artist TEXT NOT NULL,
                    album TEXT NOT NULL,
                    artwork_uri TEXT NOT NULL,
                    duration_ms INTEGER NOT NULL
                )"""
            )
        }

        override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
            if (oldVersion < 2) {
                db.execSQL("ALTER TABLE $TABLE ADD COLUMN source TEXT NOT NULL DEFAULT 'PHONE'")
                db.execSQL("ALTER TABLE $TABLE ADD COLUMN provider_id TEXT NOT NULL DEFAULT 'local'")
            }
        }
    }

    fun load(context: Context): SavedPhoneQueue? {
        val helper = QueueDatabase(context.applicationContext)
        val tracks = mutableListOf<Track>()
        try {
            helper.readableDatabase.query(
                TABLE,
                arrayOf(
                    "source", "provider_id", "track_id", "uri", "title",
                    "artist", "album", "artwork_uri", "duration_ms"
                ),
                null,
                null,
                null,
                null,
                "position ASC"
            ).use { cursor ->
                while (cursor.moveToNext()) {
                    val source = runCatching {
                        TrackSource.valueOf(cursor.getString(cursor.getColumnIndexOrThrow("source")))
                    }.getOrNull() ?: continue
                    val providerId = cursor.getString(cursor.getColumnIndexOrThrow("provider_id"))
                    val trackId = cursor.getString(cursor.getColumnIndexOrThrow("track_id"))
                    val uri = cursor.getString(cursor.getColumnIndexOrThrow("uri"))
                    if (source == TrackSource.PHONE && (!uri.startsWith("content://") || providerId != "local")) continue
                    if (source == TrackSource.BRIDGE && (providerId.isBlank() || trackId.isBlank())) continue
                    tracks += Track(
                        providerId = providerId,
                        trackId = trackId,
                        title = cursor.getString(cursor.getColumnIndexOrThrow("title")).ifBlank { "Unknown track" },
                        artist = cursor.getString(cursor.getColumnIndexOrThrow("artist")).ifBlank { "Unknown artist" },
                        album = cursor.getString(cursor.getColumnIndexOrThrow("album")),
                        streamUrl = if (source == TrackSource.PHONE) uri else "",
                        artworkUri = cursor.getString(cursor.getColumnIndexOrThrow("artwork_uri")),
                        durationMs = cursor.getLong(cursor.getColumnIndexOrThrow("duration_ms")).coerceAtLeast(0L),
                        source = source
                    )
                }
            }
        } catch (_: Exception) {
            return null
        } finally {
            helper.close()
        }
        if (tracks.isEmpty()) return null
        val preferences = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
        val index = preferences.getInt(INDEX_KEY, 0).coerceIn(0, tracks.lastIndex)
        val positionMs = preferences.getLong(POSITION_KEY, 0L).coerceAtLeast(0L)
        return SavedPhoneQueue(tracks, index, positionMs)
    }

    /** Queue writes run serially off the UI thread, including large queues. */
    fun saveAsync(
        context: Context,
        tracks: List<Track>,
        currentIndex: Int,
        currentPositionMs: Long = 0L
    ) {
        val snapshot = tracks.toList()
        writer.execute {
            save(context.applicationContext, snapshot, currentIndex, currentPositionMs)
        }
    }

    fun clearAsync(context: Context) {
        writer.execute { clear(context.applicationContext) }
    }

    private fun save(
        context: Context,
        tracks: List<Track>,
        currentIndex: Int,
        currentPositionMs: Long
    ) {
        if (tracks.isEmpty()) {
            clear(context)
            return
        }
        if (tracks.any { track ->
                track.trackId.isBlank() || when (track.source) {
                    TrackSource.PHONE -> track.providerId != "local" || !track.streamUrl.startsWith("content://")
                    TrackSource.BRIDGE -> track.providerId.isBlank()
                }
            }
        ) return

        val helper = QueueDatabase(context)
        try {
            val db = helper.writableDatabase
            db.beginTransaction()
            try {
                db.delete(TABLE, null, null)
                tracks.forEachIndexed { index, track ->
                    val values = ContentValues().apply {
                        put("position", index)
                        put("source", track.source.name)
                        put("provider_id", track.providerId)
                        put("track_id", track.trackId)
                        // Bridge URLs contain short-lived playback tokens, so never write them to disk.
                        put("uri", if (track.source == TrackSource.PHONE) track.streamUrl else "")
                        put("title", track.title)
                        put("artist", track.artist)
                        put("album", track.album)
                        put("artwork_uri", track.artworkUri)
                        put("duration_ms", track.durationMs.coerceAtLeast(0L))
                    }
                    db.insertOrThrow(TABLE, null, values)
                }
                db.setTransactionSuccessful()
            } finally {
                db.endTransaction()
            }
        } finally {
            helper.close()
        }
        context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).edit()
            .putInt(INDEX_KEY, currentIndex.coerceIn(0, tracks.lastIndex))
            .putLong(POSITION_KEY, currentPositionMs.coerceAtLeast(0L))
            .apply()
    }

    private fun clear(context: Context) {
        val helper = QueueDatabase(context)
        try {
            helper.writableDatabase.delete(TABLE, null, null)
        } finally {
            helper.close()
        }
        context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).edit()
            .remove(INDEX_KEY)
            .remove(POSITION_KEY)
            .apply()
    }

    /** Checkpoint only the active stable identity; the stream URL never leaves Media3's memory. */
    fun saveFromPlayer(context: Context, player: Player) {
        val item = player.currentMediaItem ?: return
        val positionMs = player.currentPosition.coerceAtLeast(0L)
        val parts = item.mediaId.split('|', limit = 3)
        val source: TrackSource
        val providerId: String
        val trackId: String
        if (parts.size == 3) {
            source = runCatching { TrackSource.valueOf(parts[0]) }.getOrNull() ?: return
            providerId = parts[1]
            trackId = parts[2]
        } else if (parts.size == 2 && parts[0] == "local") {
            source = TrackSource.PHONE
            providerId = "local"
            trackId = parts[1]
        } else {
            return
        }
        writer.execute {
            val helper = QueueDatabase(context.applicationContext)
            try {
                helper.readableDatabase.query(
                    TABLE,
                    arrayOf("position"),
                    "source = ? AND provider_id = ? AND track_id = ?",
                    arrayOf(source.name, providerId, trackId),
                    null,
                    null,
                    null
                ).use { cursor ->
                    if (cursor.moveToFirst()) {
                        val index = cursor.getInt(cursor.getColumnIndexOrThrow("position"))
                        context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).edit()
                            .putInt(INDEX_KEY, index)
                            .putLong(POSITION_KEY, positionMs)
                            .apply()
                    }
                }
            } finally {
                helper.close()
            }
        }
    }
}

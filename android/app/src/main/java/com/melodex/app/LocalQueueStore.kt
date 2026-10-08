package com.melodex.app

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import androidx.media3.common.Player
import java.util.concurrent.Executors

internal data class SavedLocalQueue(
    val tracks: List<Track>,
    val currentIndex: Int
)

/** Stores local MediaStore queue entries in SQLite; Bridge stream URLs may expire. */
internal object LocalQueueStore {
    private const val DATABASE = "local_playback_queue.db"
    private const val TABLE = "queue_items"
    private const val PREFERENCES = "local_playback_queue"
    private const val INDEX_KEY = "current_index"

    private val writer = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "MelodexQueueWriter").apply { isDaemon = true }
    }

    private class QueueDatabase(context: Context) :
        SQLiteOpenHelper(context, DATABASE, null, 1) {
        override fun onCreate(db: SQLiteDatabase) {
            db.execSQL(
                """CREATE TABLE $TABLE (
                    position INTEGER PRIMARY KEY NOT NULL,
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
            db.execSQL("DROP TABLE IF EXISTS $TABLE")
            onCreate(db)
        }
    }

    fun load(context: Context): SavedLocalQueue? {
        val helper = QueueDatabase(context.applicationContext)
        val tracks = mutableListOf<Track>()
        try {
            helper.readableDatabase.query(
                TABLE,
                arrayOf("track_id", "uri", "title", "artist", "album", "artwork_uri", "duration_ms"),
                null,
                null,
                null,
                null,
                "position ASC"
            ).use { cursor ->
                while (cursor.moveToNext()) {
                    val uri = cursor.getString(cursor.getColumnIndexOrThrow("uri"))
                    if (!uri.startsWith("content://")) continue
                    tracks += Track(
                        providerId = "local",
                        trackId = cursor.getString(cursor.getColumnIndexOrThrow("track_id")),
                        title = cursor.getString(cursor.getColumnIndexOrThrow("title")).ifBlank { "Unknown track" },
                        artist = cursor.getString(cursor.getColumnIndexOrThrow("artist")).ifBlank { "Unknown artist" },
                        album = cursor.getString(cursor.getColumnIndexOrThrow("album")),
                        streamUrl = uri,
                        artworkUri = cursor.getString(cursor.getColumnIndexOrThrow("artwork_uri")),
                        durationMs = cursor.getLong(cursor.getColumnIndexOrThrow("duration_ms")).coerceAtLeast(0L)
                    )
                }
            }
        } catch (_: Exception) {
            return null
        } finally {
            helper.close()
        }
        if (tracks.isEmpty()) return null
        val index = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
            .getInt(INDEX_KEY, 0)
            .coerceIn(0, tracks.lastIndex)
        return SavedLocalQueue(tracks, index)
    }

    /** Queue writes run serially off the UI thread, including very large queues. */
    fun saveAsync(context: Context, tracks: List<Track>, currentIndex: Int) {
        val snapshot = tracks.toList()
        writer.execute { save(context.applicationContext, snapshot, currentIndex) }
    }

    fun clearAsync(context: Context) {
        writer.execute { clear(context.applicationContext) }
    }

    private fun save(context: Context, tracks: List<Track>, currentIndex: Int) {
        if (tracks.isEmpty()) {
            clear(context)
            return
        }
        if (tracks.any { it.providerId != "local" || !it.streamUrl.startsWith("content://") }) return

        val helper = QueueDatabase(context)
        try {
            val db = helper.writableDatabase
            db.beginTransaction()
            try {
                db.delete(TABLE, null, null)
                tracks.forEachIndexed { index, track ->
                    val values = ContentValues().apply {
                        put("position", index)
                        put("track_id", track.trackId)
                        put("uri", track.streamUrl)
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
            .apply()
    }

    /** Persist just the index as system controls move through a saved local queue. */
    fun saveFromPlayer(context: Context, player: Player) {
        if (player.mediaItemCount == 0) return
        for (index in 0 until player.mediaItemCount) {
            if (!player.getMediaItemAt(index).mediaId.startsWith("local|")) return
        }
        savePosition(context, player.currentMediaItemIndex)
    }

    private fun savePosition(context: Context, index: Int) {
        if (index < 0) return
        context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).edit()
            .putInt(INDEX_KEY, index)
            .apply()
    }
}

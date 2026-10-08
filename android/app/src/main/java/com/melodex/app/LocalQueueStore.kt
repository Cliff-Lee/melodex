package com.melodex.app

import android.content.Context
import androidx.media3.common.Player
import org.json.JSONArray
import org.json.JSONObject

internal data class SavedLocalQueue(
    val tracks: List<Track>,
    val currentIndex: Int
)

/** Stores only local MediaStore queue entries; Bridge stream URLs may expire. */
internal object LocalQueueStore {
    private const val PREFERENCES = "local_playback_queue"
    private const val TRACKS_KEY = "tracks"
    private const val INDEX_KEY = "current_index"

    fun load(context: Context): SavedLocalQueue? {
        val preferences = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
        val encoded = preferences.getString(TRACKS_KEY, null) ?: return null
        return try {
            val array = JSONArray(encoded)
            val tracks = buildList {
                for (index in 0 until array.length()) {
                    val item = array.optJSONObject(index) ?: continue
                    val uri = item.optString("uri")
                    if (!uri.startsWith("content://")) continue
                    add(
                        Track(
                            providerId = "local",
                            trackId = item.optString("id", uri),
                            title = item.optString("title").ifBlank { "Unknown track" },
                            artist = item.optString("artist").ifBlank { "Unknown artist" },
                            album = item.optString("album"),
                            streamUrl = uri,
                            artworkUri = item.optString("artwork"),
                            durationMs = item.optLong("duration")
                        )
                    )
                }
            }
            if (tracks.isEmpty()) return null
            SavedLocalQueue(
                tracks = tracks,
                currentIndex = preferences.getInt(INDEX_KEY, 0).coerceIn(0, tracks.lastIndex)
            )
        } catch (_: Exception) {
            null
        }
    }

    fun save(context: Context, tracks: List<Track>, currentIndex: Int) {
        val localTracks = tracks.filter {
            it.providerId == "local" && it.streamUrl.startsWith("content://")
        }
        if (localTracks.isEmpty()) {
            clear(context)
            return
        }
        val array = JSONArray()
        localTracks.forEach { track ->
            array.put(
                JSONObject()
                    .put("id", track.trackId)
                    .put("uri", track.streamUrl)
                    .put("title", track.title)
                    .put("artist", track.artist)
                    .put("album", track.album)
                    .put("artwork", track.artworkUri)
                    .put("duration", track.durationMs)
            )
        }
        context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).edit()
            .putString(TRACKS_KEY, array.toString())
            .putInt(INDEX_KEY, currentIndex.coerceIn(0, localTracks.lastIndex))
            .apply()
    }

    fun clear(context: Context) {
        context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).edit()
            .remove(TRACKS_KEY)
            .remove(INDEX_KEY)
            .apply()
    }

    /** Keep the saved position current while notification or headset controls skip tracks. */
    fun saveFromPlayer(context: Context, player: Player) {
        if (player.mediaItemCount == 0) return
        val knownDurations = load(context)?.tracks?.associate { it.trackId to it.durationMs }.orEmpty()
        val tracks = mutableListOf<Track>()
        for (index in 0 until player.mediaItemCount) {
            val item = player.getMediaItemAt(index)
            if (!item.mediaId.startsWith("local|")) return
            val uri = item.localConfiguration?.uri?.toString() ?: return
            val metadata = item.mediaMetadata
            val trackId = item.mediaId.removePrefix("local|")
            tracks += Track(
                providerId = "local",
                trackId = trackId,
                title = metadata.title?.toString().orEmpty().ifBlank { "Unknown track" },
                artist = metadata.artist?.toString().orEmpty().ifBlank { "Unknown artist" },
                album = metadata.albumTitle?.toString().orEmpty(),
                streamUrl = uri,
                artworkUri = metadata.artworkUri?.toString().orEmpty(),
                durationMs = knownDurations[trackId] ?: 0L
            )
        }
        save(context, tracks, player.currentMediaItemIndex.coerceAtLeast(0))
    }
}

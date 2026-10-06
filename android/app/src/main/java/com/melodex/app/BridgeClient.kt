package com.melodex.app

import android.net.Uri
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

class BridgeClient(private val baseUrl: String, private val token: String) {
    private fun get(path: String): JSONObject {
        val address = Uri.parse(baseUrl.trim())
        if (address.scheme !in setOf("http", "https") || address.host.isNullOrBlank()) {
            throw BridgeException("Enter the full Melodex address, including http:// and port 8766.")
        }
        val normalized = baseUrl.trim().trimEnd('/')
        val connection = (URL(normalized + path).openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 5_000
            readTimeout = 12_000
            setRequestProperty("Authorization", "Bearer ${token.trim()}")
            setRequestProperty("Accept", "application/json")
        }
        try {
            val code = connection.responseCode
            if (code !in 200..299) {
                throw BridgeException(when (code) {
                    401, 403 -> "That Bridge token was not accepted. Copy the current token from Melodex."
                    404 -> "This address did not respond as a Melodex Provider Bridge. Check the address and port."
                    else -> "Melodex could not complete that request (error $code). Try again."
                })
            }
            return connection.inputStream.bufferedReader().use { JSONObject(it.readText()) }
        } finally {
            connection.disconnect()
        }
    }

    fun connect(): Int = get("/v1/providers").optJSONArray("providers")?.length() ?: 0

    fun search(query: String): List<Track> {
        val encoded = Uri.encode(query)
        val response = get("/v1/search?q=$encoded&provider=all&limit=50")
        val items = response.optJSONArray("items") ?: return emptyList()
        return buildList {
            for (i in 0 until items.length()) {
                val item = items.optJSONObject(i) ?: continue
                val provider = item.optString("provider_id")
                val trackId = item.optString("track_id")
                if (provider.isBlank() || trackId.isBlank()) continue
                add(Track(
                    id = "bridge:$provider:$trackId",
                    title = item.optString("title").ifBlank { "Unknown track" },
                    artist = item.optString("artist").ifBlank { "Unknown artist" },
                    album = item.optString("album"),
                    uri = Uri.EMPTY,
                    artworkUri = item.optString("artwork_url").takeIf(String::isNotBlank)?.let(Uri::parse),
                    source = Track.Source.BRIDGE,
                    providerId = provider,
                    remoteTrackId = trackId,
                ))
            }
        }
    }

    fun resolve(track: Track): Track {
        val provider = Uri.encode(track.providerId)
        val id = Uri.encode(track.remoteTrackId)
        val item = get("/v1/resolve?provider=$provider&id=$id")
        val stream = item.optString("stream_url").takeIf(String::isNotBlank)
            ?: throw BridgeException("The source did not provide a playable stream for this track.")
        return track.copy(
            title = item.optString("title").ifBlank { track.title },
            artist = item.optString("artist").ifBlank { track.artist },
            album = item.optString("album").ifBlank { track.album },
            uri = Uri.parse(stream),
            artworkUri = item.optString("artwork_url").takeIf(String::isNotBlank)?.let(Uri::parse) ?: track.artworkUri,
        )
    }
}

class BridgeException(message: String) : IllegalStateException(message)

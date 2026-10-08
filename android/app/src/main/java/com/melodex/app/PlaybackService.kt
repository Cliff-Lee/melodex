package com.melodex.app

import android.os.Handler
import android.os.Looper
import androidx.media3.common.AudioAttributes
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.session.MediaSession
import androidx.media3.session.MediaSessionService

/** Owns playback beyond the Activity lifecycle and publishes Android media controls. */
class PlaybackService : MediaSessionService() {
    private lateinit var player: ExoPlayer
    private var mediaSession: MediaSession? = null
    private val checkpointHandler = Handler(Looper.getMainLooper())
    private val checkpointRunnable = object : Runnable {
        override fun run() {
            if (::player.isInitialized && player.isPlaying) {
                LocalQueueStore.saveFromPlayer(this@PlaybackService, player)
                checkpointHandler.postDelayed(this, CHECKPOINT_INTERVAL_MS)
            }
        }
    }

    override fun onCreate() {
        super.onCreate()
        player = ExoPlayer.Builder(this).build().apply {
            setAudioAttributes(AudioAttributes.DEFAULT, true)
            setHandleAudioBecomingNoisy(true)
            addListener(object : Player.Listener {
                override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) {
                    if (mediaItem != null) {
                        LocalQueueStore.saveFromPlayer(this@PlaybackService, player)
                    }
                }

                override fun onIsPlayingChanged(isPlaying: Boolean) {
                    checkpointHandler.removeCallbacks(checkpointRunnable)
                    if (isPlaying) {
                        checkpointHandler.postDelayed(checkpointRunnable, CHECKPOINT_INTERVAL_MS)
                    } else {
                        LocalQueueStore.saveFromPlayer(this@PlaybackService, player)
                    }
                }
            })
        }
        mediaSession = MediaSession.Builder(this, player).build()
    }

    override fun onGetSession(controllerInfo: MediaSession.ControllerInfo): MediaSession? =
        mediaSession

    override fun onDestroy() {
        checkpointHandler.removeCallbacks(checkpointRunnable)
        if (::player.isInitialized) LocalQueueStore.saveFromPlayer(this, player)
        mediaSession?.release()
        mediaSession = null
        if (::player.isInitialized) player.release()
        super.onDestroy()
    }

    private companion object {
        const val CHECKPOINT_INTERVAL_MS = 5_000L
    }
}

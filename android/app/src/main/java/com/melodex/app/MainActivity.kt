package com.melodex.app

import android.Manifest
import android.content.pm.PackageManager
import android.content.ComponentName
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.Player
import androidx.media3.session.MediaController
import androidx.media3.session.SessionToken
import com.google.common.util.concurrent.ListenableFuture
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder


data class Track(
    val providerId: String,
    val trackId: String,
    val title: String,
    val artist: String,
    val album: String = "",
    val streamUrl: String = ""
)

private enum class MusicSource { PHONE, BRIDGE }

class BridgeClient(var baseUrl: String, var token: String) {
    private fun get(path: String): JSONObject {
        val conn = URL(baseUrl.trimEnd('/') + path).openConnection() as HttpURLConnection
        conn.requestMethod = "GET"
        conn.connectTimeout = 8000
        conn.readTimeout = 15000
        if (token.isNotBlank()) conn.setRequestProperty("Authorization", "Bearer $token")
        conn.setRequestProperty("Accept", "application/json")
        val code = conn.responseCode
        val body = (if (code in 200..299) conn.inputStream else conn.errorStream).bufferedReader().use { it.readText() }
        if (code !in 200..299) throw IllegalStateException("Bridge error $code: $body")
        return JSONObject(body)
    }

    fun health(): Boolean = get("/health").optBoolean("ok", false)

    fun search(query: String): List<Track> {
        val q = URLEncoder.encode(query, "UTF-8")
        val json = get("/v1/search?q=$q&provider=all")
        val arr = json.optJSONArray("items") ?: return emptyList()
        return buildList {
            for (i in 0 until arr.length()) {
                val x = arr.getJSONObject(i)
                add(Track(
                    providerId = x.optString("provider_id"),
                    trackId = x.optString("track_id"),
                    title = x.optString("title", "Unknown track"),
                    artist = x.optString("artist", "Unknown artist"),
                    album = x.optString("album"),
                    streamUrl = x.optString("stream_url")
                ))
            }
        }
    }

    fun resolve(track: Track): Track {
        val p = URLEncoder.encode(track.providerId, "UTF-8")
        val id = URLEncoder.encode(track.trackId, "UTF-8")
        val x = get("/v1/resolve?provider=$p&id=$id")
        return track.copy(
            title = x.optString("title", track.title),
            artist = x.optString("artist", track.artist),
            album = x.optString("album", track.album),
            streamUrl = x.optString("stream_url", track.streamUrl)
        )
    }
}

class MainActivity : ComponentActivity() {
    private var controllerFuture: ListenableFuture<MediaController>? = null
    private val controllerState = mutableStateOf<MediaController?>(null)
    private val connectionError = mutableStateOf<String?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            val controller = controllerState.value
            if (controller == null) {
                PlayerConnectionScreen(connectionError.value, ::connectToPlaybackService)
            } else {
                MelodexApp(controller)
            }
        }
    }

    override fun onStart() {
        super.onStart()
        connectToPlaybackService()
    }

    override fun onStop() {
        val future = controllerFuture
        controllerFuture = null
        controllerState.value = null
        if (future != null) MediaController.releaseFuture(future)
        super.onStop()
    }

    private fun connectToPlaybackService() {
        connectionError.value = null
        val token = SessionToken(this, ComponentName(this, PlaybackService::class.java))
        val future = MediaController.Builder(this, token).buildAsync()
        controllerFuture = future
        future.addListener({
            if (controllerFuture !== future) return@addListener
            try {
                controllerState.value = future.get()
            } catch (e: Exception) {
                connectionError.value = e.cause?.message ?: e.message ?: "Could not connect to the playback service."
            }
        }, ContextCompat.getMainExecutor(this))
    }
}

@Composable
private fun PlayerConnectionScreen(error: String?, onRetry: () -> Unit) {
    MaterialTheme(colorScheme = darkColorScheme()) {
        Surface(Modifier.fillMaxSize()) {
            Column(
                Modifier.fillMaxSize().padding(24.dp),
                verticalArrangement = Arrangement.Center,
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                if (error == null) {
                    CircularProgressIndicator()
                    Spacer(Modifier.height(16.dp))
                    Text("Starting playback…")
                } else {
                    Text("Melodex could not start its playback service.")
                    Spacer(Modifier.height(8.dp))
                    Text(error, style = MaterialTheme.typography.bodySmall)
                    Spacer(Modifier.height(16.dp))
                    Button(onClick = onRetry) { Text("Try again") }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MelodexApp(player: Player) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val audioPermission = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
        Manifest.permission.READ_MEDIA_AUDIO
    } else {
        Manifest.permission.READ_EXTERNAL_STORAGE
    }

    var musicSource by remember { mutableStateOf(MusicSource.PHONE) }
    var hasAudioPermission by remember {
        mutableStateOf(ContextCompat.checkSelfPermission(context, audioPermission) == PackageManager.PERMISSION_GRANTED)
    }
    var localStatus by remember { mutableStateOf("Choose phone music to see audio stored on this device.") }
    var localTracks by remember { mutableStateOf<List<Track>>(emptyList()) }
    var localLoading by remember { mutableStateOf(false) }
    var bridgeUrl by remember { mutableStateOf("") }
    var token by remember { mutableStateOf("") }
    var query by remember { mutableStateOf("") }
    var bridgeStatus by remember { mutableStateOf("Enter your Bridge address and token to connect.") }
    var bridgeResults by remember { mutableStateOf<List<Track>>(emptyList()) }
    var nowPlaying by remember { mutableStateOf<Track?>(null) }

    val refreshLocalLibrary: () -> Unit = {
        scope.launch {
            localLoading = true
            localStatus = "Looking for audio on this device…"
            try {
                localTracks = withContext(Dispatchers.IO) {
                    queryLocalAudioTracks(context.contentResolver, context)
                }
                localStatus = if (localTracks.isEmpty()) {
                    "No audio tracks were found on this device."
                } else {
                    "${localTracks.size} tracks on this device"
                }
            } catch (e: Exception) {
                localStatus = e.message ?: "Could not read music on this device."
            } finally {
                localLoading = false
            }
        }
    }

    val audioPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        hasAudioPermission = granted
        localStatus = if (granted) "Music access allowed." else "Music access was not allowed. You can still connect a Bridge."
    }

    LaunchedEffect(hasAudioPermission) {
        if (hasAudioPermission) refreshLocalLibrary()
    }

    fun play(track: Track) {
        val mediaItem = MediaItem.Builder()
            .setUri(track.streamUrl)
            .setMediaMetadata(
                MediaMetadata.Builder()
                    .setTitle(track.title)
                    .setArtist(track.artist)
                    .setAlbumTitle(track.album)
                    .build()
            )
            .build()
        player.setMediaItem(mediaItem)
        player.prepare()
        player.play()
        nowPlaying = track
    }

    MaterialTheme(colorScheme = darkColorScheme()) {
        Scaffold(topBar = { TopAppBar(title = { Text("Melodex") }) }) { pad ->
            Column(
                Modifier.padding(pad).padding(16.dp).fillMaxSize(),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (musicSource == MusicSource.PHONE) {
                        Button(onClick = { musicSource = MusicSource.PHONE }, modifier = Modifier.weight(1f)) {
                            Text("On this phone")
                        }
                    } else {
                        OutlinedButton(onClick = { musicSource = MusicSource.PHONE }, modifier = Modifier.weight(1f)) {
                            Text("On this phone")
                        }
                    }
                    if (musicSource == MusicSource.BRIDGE) {
                        Button(onClick = { musicSource = MusicSource.BRIDGE }, modifier = Modifier.weight(1f)) {
                            Text("Connect a Melodex")
                        }
                    } else {
                        OutlinedButton(onClick = { musicSource = MusicSource.BRIDGE }, modifier = Modifier.weight(1f)) {
                            Text("Connect a Melodex")
                        }
                    }
                }

                Text(
                    if (musicSource == MusicSource.PHONE) "Play music on this phone" else "Connect to another Melodex",
                    style = MaterialTheme.typography.titleMedium
                )

                if (musicSource == MusicSource.PHONE) {
                    if (!hasAudioPermission) {
                        Column(Modifier.fillMaxWidth().weight(1f), verticalArrangement = Arrangement.Center) {
                            Card(Modifier.fillMaxWidth()) {
                                Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                                    Text("Your music stays on this device.", style = MaterialTheme.typography.titleSmall)
                                    Text("Allow audio access so Melodex can list music Android has indexed on your phone.")
                                    Button(onClick = { audioPermissionLauncher.launch(audioPermission) }) {
                                        Text("Allow music access")
                                    }
                                }
                            }
                        }
                    } else {
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                            Text(localStatus, modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodySmall)
                            TextButton(onClick = refreshLocalLibrary, enabled = !localLoading) {
                                Text(if (localLoading) "Loading…" else "Refresh")
                            }
                        }
                        Button(
                            onClick = {
                                localTracks.randomOrNull()?.let { track ->
                                    try {
                                        play(track)
                                    } catch (e: Exception) {
                                        localStatus = e.message ?: "Could not play this track."
                                    }
                                }
                            },
                            enabled = localTracks.isNotEmpty() && !localLoading,
                            modifier = Modifier.fillMaxWidth()
                        ) { Text("Play something") }
                        TrackList(localTracks, onSelect = { track ->
                            try {
                                play(track)
                            } catch (e: Exception) {
                                localStatus = e.message ?: "Could not play this track."
                            }
                        }, modifier = Modifier.weight(1f))
                    }
                } else {
                    Column(Modifier.fillMaxWidth().weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedTextField(
                            bridgeUrl,
                            { bridgeUrl = it },
                            label = { Text("Bridge URL") },
                            placeholder = { Text("http://192.168.1.20:8766") },
                            singleLine = true,
                            modifier = Modifier.fillMaxWidth()
                        )
                        OutlinedTextField(
                            token,
                            { token = it },
                            label = { Text("Bridge token") },
                            visualTransformation = PasswordVisualTransformation(),
                            singleLine = true,
                            modifier = Modifier.fillMaxWidth()
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                            Button(onClick = {
                                scope.launch {
                                    bridgeStatus = "Connecting…"
                                    bridgeStatus = try {
                                        val ok = withContext(Dispatchers.IO) { BridgeClient(bridgeUrl, token).health() }
                                        if (ok) "Connected." else "Bridge did not report healthy."
                                    } catch (e: Exception) { e.message ?: "Connection failed" }
                                }
                            }) { Text("Connect") }
                            Text(bridgeStatus, modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodySmall)
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                            OutlinedTextField(
                                query,
                                { query = it },
                                label = { Text("Search connected music") },
                                singleLine = true,
                                modifier = Modifier.weight(1f)
                            )
                            Button(onClick = {
                                scope.launch {
                                    bridgeStatus = "Searching…"
                                    try {
                                        bridgeResults = withContext(Dispatchers.IO) {
                                            BridgeClient(bridgeUrl, token).search(query)
                                        }
                                        bridgeStatus = "${bridgeResults.size} results"
                                    } catch (e: Exception) {
                                        bridgeStatus = e.message ?: "Search failed"
                                    }
                                }
                            }) { Text("Search") }
                        }
                        TrackList(bridgeResults, onSelect = { track ->
                            scope.launch {
                                bridgeStatus = "Resolving…"
                                try {
                                    val resolved = withContext(Dispatchers.IO) {
                                        BridgeClient(bridgeUrl, token).resolve(track)
                                    }
                                    if (resolved.streamUrl.isBlank()) {
                                        throw IllegalStateException("Source did not return a stream URL")
                                    }
                                    play(resolved)
                                    bridgeStatus = "Playing"
                                } catch (e: Exception) {
                                    bridgeStatus = e.message ?: "Playback failed"
                                }
                            }
                        }, modifier = Modifier.weight(1f))
                    }
                }

                nowPlaying?.let {
                    Text("Now playing: ${it.artist} — ${it.title}", style = MaterialTheme.typography.titleSmall)
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = { if (player.isPlaying) player.pause() else player.play() }) {
                        Text("Play / Pause")
                    }
                    OutlinedButton(onClick = { player.seekTo(0) }) { Text("Restart") }
                }
            }
        }
    }
}

@Composable
private fun TrackList(tracks: List<Track>, onSelect: (Track) -> Unit, modifier: Modifier = Modifier) {
    LazyColumn(modifier) {
        items(tracks) { track ->
            ListItem(
                headlineContent = { Text(track.title) },
                supportingContent = {
                    Text("${track.artist}${if (track.album.isNotBlank()) " · ${track.album}" else ""}")
                },
                modifier = Modifier.clickable { onSelect(track) }
            )
            HorizontalDivider()
        }
    }
}

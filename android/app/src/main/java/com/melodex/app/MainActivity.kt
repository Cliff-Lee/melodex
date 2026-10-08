package com.melodex.app

import android.Manifest
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.media.MediaMetadataRetriever
import android.net.Uri
import android.util.Size
import android.content.pm.PackageManager
import android.content.ComponentName
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
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
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
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
    val streamUrl: String = "",
    val artworkUri: String = "",
    val durationMs: Long = 0L
)

private enum class MusicSource { PHONE, BRIDGE }

private enum class LocalSort(val label: String) {
    TITLE("Title"),
    ARTIST("Artist"),
    ALBUM("Album")
}

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

    private fun post(path: String, body: JSONObject): JSONObject {
        val conn = URL(baseUrl.trimEnd('/') + path).openConnection() as HttpURLConnection
        conn.requestMethod = "POST"
        conn.connectTimeout = 8000
        conn.readTimeout = 15000
        conn.doOutput = true
        conn.setRequestProperty("Accept", "application/json")
        conn.setRequestProperty("Content-Type", "application/json; charset=utf-8")
        if (token.isNotBlank()) conn.setRequestProperty("Authorization", "Bearer $token")
        conn.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
        val code = conn.responseCode
        val response = (if (code in 200..299) conn.inputStream else conn.errorStream)
            .bufferedReader().use { it.readText() }
        if (code !in 200..299) throw IllegalStateException("Bridge error $code: $response")
        return JSONObject(response)
    }

    fun health(): Boolean = get("/health").optBoolean("ok", false)

    fun verify(): Boolean {
        get("/v1/providers")
        return true
    }

    fun pair(code: String, deviceName: String): JSONObject = post(
        "/v1/pair",
        JSONObject().put("code", code).put("device_name", deviceName)
    )

    fun unpair(deviceId: String): Boolean = post(
        "/v1/unpair",
        JSONObject().put("device_id", deviceId)
    ).optBoolean("ok", false)

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
    var localError by remember { mutableStateOf<String?>(null) }
    var localTracks by remember { mutableStateOf<List<Track>>(emptyList()) }
    var localLoading by remember { mutableStateOf(false) }
    var localSearch by remember { mutableStateOf("") }
    var localSort by remember { mutableStateOf(LocalSort.TITLE) }
    var sortMenuExpanded by remember { mutableStateOf(false) }
    var localQueue by remember { mutableStateOf<List<Track>>(emptyList()) }
    var queueDialogOpen by remember { mutableStateOf(false) }
    var bridgeUrl by remember { mutableStateOf("") }
    var token by remember { mutableStateOf("") }
    var bridgeName by remember { mutableStateOf("") }
    var bridgeDeviceId by remember { mutableStateOf("") }
    var showAdvancedBridgeSetup by remember { mutableStateOf(false) }
    var query by remember { mutableStateOf("") }
    var bridgeStatus by remember { mutableStateOf("Pairing is optional. Scan a desktop QR code to connect.") }
    var bridgeResults by remember { mutableStateOf<List<Track>>(emptyList()) }
    var nowPlaying by remember { mutableStateOf<Track?>(null) }

    val scanOptions = remember {
        ScanOptions().apply {
            setDesiredBarcodeFormats(ScanOptions.QR_CODE)
            setPrompt("Scan the QR code shown by your Melodex computer")
            setBeepEnabled(false)
            setOrientationLocked(false)
        }
    }
    val scanQrLauncher = rememberLauncherForActivityResult(ScanContract()) { result ->
        val rawCode = result.contents
        if (rawCode.isNullOrBlank()) {
            bridgeStatus = "QR scan cancelled."
        } else {
            scope.launch {
                bridgeStatus = "Pairing with your computer…"
                try {
                    val pairing = withContext(Dispatchers.IO) {
                        BridgePairingPayloadParser.parse(rawCode)
                    }
                    val deviceName = "Android ${Build.MODEL}".trim()
                    val enrolled = withContext(Dispatchers.IO) {
                        BridgeClient(pairing.baseUrl, "").pair(pairing.code, deviceName)
                    }
                    val bridgeToken = enrolled.getString("token")
                    val deviceId = enrolled.getString("device_id")
                    val displayName = enrolled.optString("device_name", pairing.displayName)
                    val connected = withContext(Dispatchers.IO) {
                        BridgeClient(pairing.baseUrl, bridgeToken).verify()
                    }
                    if (!connected) throw IllegalStateException("The Bridge did not accept this pairing.")
                    withContext(Dispatchers.IO) {
                        BridgeConnectionStore.save(
                            context.applicationContext,
                            StoredBridgeConnection(pairing.baseUrl, bridgeToken, displayName, deviceId)
                        )
                    }
                    bridgeUrl = pairing.baseUrl
                    token = bridgeToken
                    bridgeName = displayName
                    bridgeDeviceId = deviceId
                    bridgeResults = emptyList()
                    bridgeStatus = "Connected to $displayName."
                    musicSource = MusicSource.BRIDGE
                } catch (e: Exception) {
                    bridgeStatus = e.message ?: "Could not pair with that Bridge."
                }
            }
        }
    }
    val cameraPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            scanQrLauncher.launch(scanOptions)
        } else {
            bridgeStatus = "Camera access is needed to scan a pairing code."
        }
    }

    fun startQrScan() {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            scanQrLauncher.launch(scanOptions)
        } else {
            cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
        }
    }

    fun connectBridge(url: String, bridgeToken: String, displayName: String = "Melodex computer", deviceId: String = "") {
        val normalizedUrl = url.trim().trimEnd('/')
        val normalizedToken = bridgeToken.trim()
        if (normalizedUrl.isBlank() || normalizedToken.isBlank()) {
            bridgeStatus = "Enter the Bridge address and token."
            return
        }
        scope.launch {
            bridgeStatus = "Connecting…"
            try {
                val connected = withContext(Dispatchers.IO) {
                    BridgeClient(normalizedUrl, normalizedToken).verify()
                }
                if (!connected) throw IllegalStateException("The Bridge did not accept this token.")
                withContext(Dispatchers.IO) {
                    BridgeConnectionStore.save(
                        context.applicationContext,
                        StoredBridgeConnection(normalizedUrl, normalizedToken, displayName, deviceId)
                    )
                }
                bridgeUrl = normalizedUrl
                token = normalizedToken
                bridgeName = displayName
                bridgeDeviceId = deviceId
                bridgeStatus = "Connected to $displayName."
            } catch (e: Exception) {
                bridgeStatus = e.message ?: "Connection failed."
            }
        }
    }

    fun forgetBridge() {
        val currentUrl = bridgeUrl
        val currentToken = token
        val currentDeviceId = bridgeDeviceId
        scope.launch {
            var revoked = currentDeviceId.isBlank()
            if (currentDeviceId.isNotBlank()) {
                try {
                    revoked = withContext(Dispatchers.IO) {
                        BridgeClient(currentUrl, currentToken).unpair(currentDeviceId)
                    }
                } catch (_: Exception) {
                    revoked = false
                }
            }
            withContext(Dispatchers.IO) {
                BridgeConnectionStore.clear(context.applicationContext)
            }
            bridgeUrl = ""
            token = ""
            bridgeName = ""
            bridgeDeviceId = ""
            bridgeResults = emptyList()
            showAdvancedBridgeSetup = false
            bridgeStatus = if (revoked) {
                "Saved Bridge connection removed from this phone."
            } else {
                "Removed from this phone. If the computer is offline, revoke this phone in its Bridge settings."
            }
        }
    }

    LaunchedEffect(context) {
        val saved = withContext(Dispatchers.IO) {
            BridgeConnectionStore.load(context.applicationContext)
        }
        if (saved != null) {
            bridgeUrl = saved.baseUrl
            token = saved.token
            bridgeName = saved.displayName
            bridgeDeviceId = saved.deviceId
            bridgeStatus = "Checking the saved connection…"
            bridgeStatus = try {
                withContext(Dispatchers.IO) {
                    BridgeClient(saved.baseUrl, saved.token).verify()
                }
                "Connected to ${saved.displayName}."
            } catch (e: Exception) {
                "Saved connection to ${saved.displayName} is unavailable: ${e.message ?: "check the local network"}."
            }
        }
    }

    val visibleLocalTracks = remember(localTracks, localSearch, localSort) {
        val needle = localSearch.trim()
        val comparator: Comparator<Track> = when (localSort) {
            LocalSort.TITLE -> compareBy<Track, String>(String.CASE_INSENSITIVE_ORDER) { track -> track.title }.thenBy { it.artist }
            LocalSort.ARTIST -> compareBy<Track, String>(String.CASE_INSENSITIVE_ORDER) { track -> track.artist }.thenBy { it.title }
            LocalSort.ALBUM -> compareBy<Track, String>(String.CASE_INSENSITIVE_ORDER) { track -> track.album.ifBlank { track.title } }.thenBy { it.title }
        }
        localTracks
            .filter { track ->
                needle.isBlank() ||
                    track.title.contains(needle, ignoreCase = true) ||
                    track.artist.contains(needle, ignoreCase = true) ||
                    track.album.contains(needle, ignoreCase = true)
            }
            .sortedWith(comparator)
    }

    val refreshLocalLibrary: () -> Unit = {
        scope.launch {
            localLoading = true
            localError = null
            localStatus = "Finding music on this phone…"
            try {
                val preview = withContext(Dispatchers.IO) {
                    queryLocalAudioTracks(
                        context.contentResolver,
                        context,
                        limitPerVolume = LOCAL_AUDIO_PREVIEW_SIZE
                    )
                }
                localTracks = preview
                if (preview.isNotEmpty()) {
                    localStatus = "Found ${preview.size} tracks. Loading the rest of your library…"
                }

                val completeLibrary = withContext(Dispatchers.IO) {
                    queryLocalAudioTracks(context.contentResolver, context)
                }
                localTracks = completeLibrary
                localStatus = if (completeLibrary.isEmpty()) {
                    "No audio tracks were found on this device."
                } else {
                    "${completeLibrary.size} tracks on this device"
                }
            } catch (e: Exception) {
                localError = e.message ?: "Could not read music on this device."
                localStatus = if (localTracks.isEmpty()) {
                    localError ?: "Could not read music on this device."
                } else {
                    "Showing the tracks found so far. Could not finish loading the library."
                }
            } finally {
                localLoading = false
            }
        }
    }

    val audioPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        hasAudioPermission = granted
        localStatus = if (granted) {
            "Music access allowed."
        } else {
            "Music access was not allowed. You can still connect a Bridge."
        }
    }

    LaunchedEffect(hasAudioPermission) {
        if (hasAudioPermission) refreshLocalLibrary()
    }

    LaunchedEffect(player, hasAudioPermission) {
        if (!hasAudioPermission) return@LaunchedEffect
        val savedQueue = withContext(Dispatchers.IO) { LocalQueueStore.load(context) }
        if (savedQueue != null) {
            localQueue = savedQueue.tracks
            nowPlaying = savedQueue.tracks.getOrNull(savedQueue.currentIndex)
            if (player.mediaItemCount == 0) {
                player.setMediaItems(
                    savedQueue.tracks.map(::trackToMediaItem),
                    savedQueue.currentIndex,
                    0L
                )
                player.prepare()
            }
        }
    }

    val latestQueue = rememberUpdatedState(localQueue)
    DisposableEffect(player) {
        val listener = object : Player.Listener {
            override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) {
                if (mediaItem?.mediaId?.startsWith("local|") == true) {
                    nowPlaying = latestQueue.value.getOrNull(player.currentMediaItemIndex)
                }
            }
        }
        player.addListener(listener)
        onDispose { player.removeListener(listener) }
    }

    fun startLocalQueue(track: Track, candidates: List<Track>) {
        val queue = if (candidates.any { it.trackId == track.trackId }) candidates else listOf(track)
        val startIndex = queue.indexOfFirst { it.trackId == track.trackId }.coerceAtLeast(0)
        localQueue = queue
        nowPlaying = track
        player.setMediaItems(queue.map(::trackToMediaItem), startIndex, 0L)
        player.prepare()
        player.play()
        LocalQueueStore.saveAsync(context, queue, startIndex)
    }

    fun addToLocalQueue(track: Track) {
        if (localQueue.any { it.trackId == track.trackId }) {
            localStatus = "That track is already in the queue."
            return
        }
        val wasPlayingLocalQueue = player.hasOnlyLocalItems()
        val updatedQueue = localQueue + track
        localQueue = updatedQueue
        if (wasPlayingLocalQueue) {
            val currentTrackId = player.currentMediaItem?.mediaId?.removePrefix("local|")
            val currentIndex = updatedQueue.indexOfFirst { it.trackId == currentTrackId }.coerceAtLeast(0)
            player.setMediaItems(
                updatedQueue.map(::trackToMediaItem),
                currentIndex,
                player.currentPosition
            )
            player.prepare()
        }
        val savedIndex = if (wasPlayingLocalQueue) player.currentMediaItemIndex else 0
        LocalQueueStore.saveAsync(context, updatedQueue, savedIndex.coerceAtLeast(0))
        localStatus = "Added to queue: ${track.title}"
    }

    fun removeFromLocalQueue(index: Int) {
        if (index !in localQueue.indices) return
        val wasPlayingLocalQueue = player.hasOnlyLocalItems()
        val currentTrackId = player.currentMediaItem?.mediaId?.removePrefix("local|")
        val updatedQueue = localQueue.toMutableList().also { it.removeAt(index) }
        localQueue = updatedQueue
        if (wasPlayingLocalQueue) {
            if (updatedQueue.isEmpty()) {
                player.clearMediaItems()
                nowPlaying = null
            } else {
                val nextIndex = updatedQueue.indexOfFirst { it.trackId == currentTrackId }
                    .takeIf { it >= 0 }
                    ?: index.coerceIn(0, updatedQueue.lastIndex)
                player.setMediaItems(updatedQueue.map(::trackToMediaItem), nextIndex, player.currentPosition)
                player.prepare()
                nowPlaying = updatedQueue[nextIndex]
            }
        }
        if (updatedQueue.isEmpty()) {
            LocalQueueStore.clearAsync(context)
        } else {
            LocalQueueStore.saveAsync(context, updatedQueue, player.currentMediaItemIndex.coerceAtLeast(0))
        }
    }

    fun clearLocalQueue() {
        if (player.hasOnlyLocalItems()) {
            player.clearMediaItems()
            nowPlaying = null
        }
        localQueue = emptyList()
        LocalQueueStore.clearAsync(context)
        queueDialogOpen = false
    }

    fun playBridgeTrack(track: Track) {
        player.setMediaItem(trackToMediaItem(track))
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
                        Column(Modifier.fillMaxWidth().weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                                Text(
                                    localStatus,
                                    modifier = Modifier.weight(1f),
                                    style = MaterialTheme.typography.bodySmall,
                                    color = if (localError == null) MaterialTheme.colorScheme.onSurfaceVariant
                                    else MaterialTheme.colorScheme.error
                                )
                                TextButton(onClick = refreshLocalLibrary, enabled = !localLoading) {
                                    Text(if (localLoading) "Loading…" else "Refresh")
                                }
                            }
                            if (localLoading) LinearProgressIndicator(Modifier.fillMaxWidth())

                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                OutlinedTextField(
                                    value = localSearch,
                                    onValueChange = { localSearch = it },
                                    label = { Text("Search phone music") },
                                    singleLine = true,
                                    modifier = Modifier.weight(1f)
                                )
                                Box {
                                    TextButton(onClick = { sortMenuExpanded = true }) {
                                        Text("Sort: ${localSort.label}")
                                    }
                                    DropdownMenu(
                                        expanded = sortMenuExpanded,
                                        onDismissRequest = { sortMenuExpanded = false }
                                    ) {
                                        LocalSort.values().forEach { option ->
                                            DropdownMenuItem(
                                                text = { Text(option.label) },
                                                onClick = {
                                                    localSort = option
                                                    sortMenuExpanded = false
                                                }
                                            )
                                        }
                                    }
                                }
                            }

                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                Button(
                                    onClick = {
                                        visibleLocalTracks.randomOrNull()?.let { track ->
                                            startLocalQueue(track, visibleLocalTracks)
                                        }
                                    },
                                    enabled = visibleLocalTracks.isNotEmpty(),
                                    modifier = Modifier.weight(1f)
                                ) { Text("Play something") }
                                OutlinedButton(
                                    onClick = { queueDialogOpen = true },
                                    enabled = localQueue.isNotEmpty()
                                ) { Text("Queue (${localQueue.size})") }
                            }

                            when {
                                localTracks.isEmpty() && localLoading -> {
                                    Box(
                                        Modifier.fillMaxWidth().weight(1f),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                            CircularProgressIndicator()
                                            Spacer(Modifier.height(10.dp))
                                            Text("Finding tracks so you can start listening…")
                                        }
                                    }
                                }
                                localTracks.isEmpty() -> {
                                    Card(Modifier.fillMaxWidth().weight(1f)) {
                                        Column(
                                            Modifier.fillMaxWidth().padding(20.dp),
                                            verticalArrangement = Arrangement.spacedBy(8.dp)
                                        ) {
                                            Text(
                                                if (localError == null) "No tracks found" else "Could not load music",
                                                style = MaterialTheme.typography.titleMedium
                                            )
                                            Text(localError ?: "Add music to your phone, then refresh the library.")
                                            Button(onClick = refreshLocalLibrary, enabled = !localLoading) {
                                                Text("Refresh library")
                                            }
                                        }
                                    }
                                }
                                visibleLocalTracks.isEmpty() -> {
                                    Box(
                                        Modifier.fillMaxWidth().weight(1f),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Text("No tracks match “$localSearch”. Try another search.")
                                    }
                                }
                                else -> {
                                    TrackList(
                                        tracks = visibleLocalTracks,
                                        onSelect = { track -> startLocalQueue(track, visibleLocalTracks) },
                                        onAddToQueue = ::addToLocalQueue,
                                        showQueueAction = true,
                                        modifier = Modifier.weight(1f)
                                    )
                                }
                            }
                            if (localLoading && localTracks.isNotEmpty()) {
                                Text(
                                    "You can play these tracks while the rest of the library loads.",
                                    style = MaterialTheme.typography.bodySmall
                                )
                            }
                        }
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
                                    playBridgeTrack(resolved)
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

        if (queueDialogOpen) {
            AlertDialog(
                onDismissRequest = { queueDialogOpen = false },
                title = { Text("Play queue (${localQueue.size})") },
                text = {
                    if (localQueue.isEmpty()) {
                        Text("Your queue is empty. Add a track from the phone library.")
                    } else {
                        LazyColumn(Modifier.heightIn(max = 420.dp)) {
                            itemsIndexed(localQueue, key = { index, track -> "${index}:${track.trackId}" }) { index, track ->
                                ListItem(
                                    leadingContent = { TrackArtwork(track, Modifier.size(48.dp)) },
                                    headlineContent = { Text(track.title) },
                                    supportingContent = { Text("${track.artist}${if (track.album.isNotBlank()) " · ${track.album}" else ""}") },
                                    trailingContent = {
                                        TextButton(onClick = { removeFromLocalQueue(index) }) { Text("Remove") }
                                    },
                                    modifier = Modifier.clickable {
                                        player.setMediaItems(localQueue.map(::trackToMediaItem), index, 0L)
                                        player.prepare()
                                        player.play()
                                        nowPlaying = track
                                        LocalQueueStore.saveAsync(context, localQueue, index)
                                        queueDialogOpen = false
                                    }
                                )
                                HorizontalDivider()
                            }
                        }
                    }
                },
                confirmButton = {
                    TextButton(onClick = { queueDialogOpen = false }) { Text("Done") }
                },
                dismissButton = {
                    if (localQueue.isNotEmpty()) {
                        TextButton(onClick = ::clearLocalQueue) { Text("Clear queue") }
                    }
                }
            )
        }
    }
}

@Composable
private fun TrackList(
    tracks: List<Track>,
    onSelect: (Track) -> Unit,
    modifier: Modifier = Modifier,
    onAddToQueue: (Track) -> Unit = {},
    showQueueAction: Boolean = false
) {
    LazyColumn(modifier) {
        itemsIndexed(tracks, key = { _, track -> "${track.providerId}:${track.trackId}" }) { _, track ->
            val details = listOf(
                track.artist,
                track.album.takeIf(String::isNotBlank),
                formatDuration(track.durationMs).takeIf(String::isNotBlank)
            ).filterNotNull().filter(String::isNotBlank).joinToString(" · ")
            ListItem(
                leadingContent = { TrackArtwork(track, Modifier.size(52.dp)) },
                headlineContent = { Text(track.title) },
                supportingContent = { Text(details) },
                trailingContent = {
                    if (showQueueAction) {
                        TextButton(onClick = { onAddToQueue(track) }) { Text("Queue") }
                    }
                },
                modifier = Modifier.clickable { onSelect(track) }
            )
            HorizontalDivider()
        }
    }
}

@Composable
private fun TrackArtwork(track: Track, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val bitmap by produceState<Bitmap?>(initialValue = null, key1 = track.trackId, key2 = track.streamUrl) {
        value = withContext(Dispatchers.IO) { loadTrackArtwork(context, track) }
    }
    if (bitmap != null) {
        Image(
            bitmap = bitmap!!.asImageBitmap(),
            contentDescription = track.album.takeIf(String::isNotBlank)?.let { "$it artwork" } ?: "Album artwork",
            contentScale = ContentScale.Crop,
            modifier = modifier.clip(RoundedCornerShape(6.dp))
        )
    } else {
        Box(
            modifier
                .clip(RoundedCornerShape(6.dp))
                .background(MaterialTheme.colorScheme.surfaceVariant),
            contentAlignment = Alignment.Center
        ) {
            Text("♫", style = MaterialTheme.typography.titleMedium)
        }
    }
}

private fun loadTrackArtwork(context: Context, track: Track): Bitmap? {
    if (!track.streamUrl.startsWith("content://")) return null
    val audioUri = Uri.parse(track.streamUrl)
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
        try {
            return context.contentResolver.loadThumbnail(audioUri, Size(128, 128), null)
        } catch (_: Exception) {
            // Older MediaStore entries may not expose a generated thumbnail.
        }
    }

    val retriever = MediaMetadataRetriever()
    return try {
        retriever.setDataSource(context, audioUri)
        val bytes = retriever.embeddedPicture ?: return null
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) return null
        val options = BitmapFactory.Options()
        var sampleSize = 1
        while (bounds.outWidth / (sampleSize * 2) >= 128 &&
            bounds.outHeight / (sampleSize * 2) >= 128
        ) {
            sampleSize *= 2
        }
        options.inSampleSize = sampleSize
        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, options)
    } catch (_: Exception) {
        null
    } finally {
        retriever.release()
    }
}

private fun trackToMediaItem(track: Track): MediaItem {
    val metadata = MediaMetadata.Builder()
        .setTitle(track.title.ifBlank { "Unknown track" })
        .setArtist(track.artist.ifBlank { "Unknown artist" })
        .setAlbumTitle(track.album)
        .apply {
            if (track.artworkUri.isNotBlank()) setArtworkUri(Uri.parse(track.artworkUri))
        }
        .build()
    return MediaItem.Builder()
        .setMediaId("${track.providerId}|${track.trackId}")
        .setUri(track.streamUrl)
        .setMediaMetadata(metadata)
        .build()
}

private fun Player.hasOnlyLocalItems(): Boolean =
    mediaItemCount > 0 && (0 until mediaItemCount).all {
        getMediaItemAt(it).mediaId.startsWith("local|")
    }

private fun formatDuration(durationMs: Long): String {
    if (durationMs <= 0L) return ""
    val seconds = durationMs / 1000L
    return "${seconds / 60}:${(seconds % 60).toString().padStart(2, '0')}"
}

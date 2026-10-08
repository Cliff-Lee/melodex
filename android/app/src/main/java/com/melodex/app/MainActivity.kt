package com.melodex.app

import android.Manifest
import android.content.Context
import android.content.Intent
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
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
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.LifecycleOwner
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.Player
import androidx.media3.session.MediaController
import androidx.media3.session.SessionToken
import com.google.common.util.concurrent.ListenableFuture
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import kotlin.math.roundToLong
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder


private const val PRIVACY_POLICY_URL = "https://github.com/Cliff-Lee/melodex/blob/main/docs/PRIVACY.md"
private const val BRIDGE_CONNECTION_POLL_INTERVAL_MS = 15_000L
private const val BRIDGE_VERIFY_TIMEOUT_MS = 4_000
private const val BRIDGE_HANDOFF_TIMEOUT_MS = 15_000L
private const val BRIDGE_HANDOFF_POLL_INTERVAL_MS = 250L

data class Track(
    val providerId: String,
    val trackId: String,
    val title: String,
    val artist: String,
    val album: String = "",
    val streamUrl: String = "",
    val artworkUri: String = "",
    val durationMs: Long = 0L,
    val source: TrackSource = TrackSource.PHONE
)

enum class TrackSource { PHONE, BRIDGE }

private fun Track.queueKey(): String = "$source|$providerId|$trackId"

private fun JSONObject.matchesBridgeQueue(tracks: List<Track>, index: Int): Boolean {
    val desktopQueue = optJSONArray("queue") ?: return false
    if (desktopQueue.length() != tracks.size || optInt("index", -1) != index) return false
    for (queueIndex in tracks.indices) {
        val item = desktopQueue.optJSONObject(queueIndex) ?: return false
        val expected = tracks[queueIndex]
        if (
            item.optString("provider_id") != expected.providerId ||
            item.optString("track_id") != expected.trackId
        ) return false
    }
    return true
}

private enum class MusicSource { PHONE, BRIDGE }

private enum class BridgeConnectionState { UNPAIRED, CHECKING, CONNECTED, UNAVAILABLE }

data class DesktopPlaybackSnapshot(
    val isPlaying: Boolean,
    val positionMs: Long,
    val currentIndex: Int,
    val currentTrack: Track?,
    val queue: List<Track>
)

private enum class LocalSort(val label: String) {
    TITLE("Title"),
    ARTIST("Artist"),
    ALBUM("Album")
}

private val MelodexColorScheme = darkColorScheme(
    primary = Color(0xFF89D8FF),
    onPrimary = Color(0xFF07131E),
    secondary = Color(0xFFC49BFF),
    tertiary = Color(0xFF8B9BFF),
    background = Color(0xFF080B20),
    onBackground = Color(0xFFEAF0FF),
    surface = Color(0xFF11182D),
    onSurface = Color(0xFFEAF0FF),
    surfaceVariant = Color(0xFF202A43),
    onSurfaceVariant = Color(0xFFB4C1D8)
)

class BridgeClient(var baseUrl: String, var token: String) {
    private fun get(path: String, timeoutMs: Int = 8000, readTimeoutMs: Int = 15000): JSONObject {
        val conn = URL(baseUrl.trimEnd('/') + path).openConnection() as HttpURLConnection
        conn.requestMethod = "GET"
        conn.connectTimeout = timeoutMs
        conn.readTimeout = readTimeoutMs
        if (token.isNotBlank()) conn.setRequestProperty("Authorization", "Bearer $token")
        conn.setRequestProperty("Accept", "application/json")
        val code = conn.responseCode
        val body = (if (code in 200..299) conn.inputStream else conn.errorStream).bufferedReader().use { it.readText() }
        if (code !in 200..299) throw IllegalStateException("Bridge error $code: $body")
        return JSONObject(body)
    }

    private fun post(path: String, body: JSONObject, timeoutMs: Int = 8000, readTimeoutMs: Int = 15000): JSONObject {
        val conn = URL(baseUrl.trimEnd('/') + path).openConnection() as HttpURLConnection
        conn.requestMethod = "POST"
        conn.connectTimeout = timeoutMs
        conn.readTimeout = readTimeoutMs
        conn.doOutput = true
        conn.setRequestProperty("Accept", "application/json")
        conn.setRequestProperty("Content-Type", "application/json; charset=utf-8")
        if (token.isNotBlank()) conn.setRequestProperty("Authorization", "Bearer $token")
        conn.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
        val code = conn.responseCode
        val response = (if (code in 200..299) conn.inputStream else conn.errorStream)
            .bufferedReader().use { it.readText() }
        if (code !in 200..299) {
            val detail = runCatching { JSONObject(response).optString("error").takeIf { it.isNotBlank() } }.getOrNull()
                ?: response
            throw IllegalStateException("Bridge error $code: $detail")
        }
        return JSONObject(response)
    }

    fun health(): Boolean = get("/health").optBoolean("ok", false)

    fun verify(): Boolean {
        get(
            "/v1/providers",
            timeoutMs = BRIDGE_VERIFY_TIMEOUT_MS,
            readTimeoutMs = BRIDGE_VERIFY_TIMEOUT_MS
        )
        return true
    }

    fun pair(code: String, deviceName: String): JSONObject = post(
        "/v1/pair",
        JSONObject().put("code", code).put("device_name", deviceName)
    )

    fun unpair(deviceId: String, timeoutMs: Int = 8000): Boolean = post(
        "/v1/unpair",
        JSONObject().put("device_id", deviceId),
        timeoutMs = timeoutMs,
        readTimeoutMs = timeoutMs
    ).optBoolean("ok", false)

    fun status(): JSONObject = get(
        "/v1/status",
        timeoutMs = BRIDGE_VERIFY_TIMEOUT_MS,
        readTimeoutMs = BRIDGE_VERIFY_TIMEOUT_MS
    )

    fun browse(providerId: String = "local", kind: String = "featured"): List<Track> {
        val provider = URLEncoder.encode(providerId, "UTF-8")
        val browseKind = URLEncoder.encode(kind, "UTF-8")
        val json = get("/v1/browse?provider=$provider&kind=$browseKind")
        return parseBridgeTrackArray(json.optJSONArray("items"))
    }

    fun playbackSnapshot(): DesktopPlaybackSnapshot {
        val json = status()
        val queue = parseBridgeTrackArray(json.optJSONArray("queue"))
        val index = json.optInt("index", -1)
        return DesktopPlaybackSnapshot(
            isPlaying = json.optBoolean("playing", false),
            positionMs = json.optLong("position_ms", 0L).coerceAtLeast(0L),
            currentIndex = index,
            currentTrack = parseBridgeTrack(json.optJSONObject("current_track")) ?: queue.getOrNull(index),
            queue = queue
        )
    }

    private fun parseBridgeTrack(item: JSONObject?, includeStreamUrl: Boolean = false): Track? {
        if (item == null) return null
        val providerId = item.optString("provider_id").takeIf { it.isNotBlank() } ?: return null
        val trackId = item.optString("track_id").takeIf { it.isNotBlank() } ?: return null
        return Track(
            providerId = providerId,
            trackId = trackId,
            title = item.optString("title", "Unknown track"),
            artist = item.optString("artist", "Unknown artist"),
            album = item.optString("album"),
            streamUrl = if (includeStreamUrl) item.optString("stream_url") else "",
            durationMs = item.optLong("duration_ms", 0L).coerceAtLeast(0L),
            source = TrackSource.BRIDGE
        )
    }

    private fun parseBridgeTrackArray(items: JSONArray?): List<Track> {
        if (items == null) return emptyList()
        return buildList {
            for (index in 0 until items.length()) {
                parseBridgeTrack(items.optJSONObject(index))?.let { add(it) }
            }
        }
    }

    fun handoffToDesktop(
        tracks: List<Track>,
        start: Int,
        positionMs: Long
    ): JSONObject {
        val queue = JSONArray()
        tracks.forEach { track ->
            queue.put(
                JSONObject()
                    .put("source", "bridge")
                    .put("provider_id", track.providerId)
                    .put("track_id", track.trackId)
                    .put("title", track.title)
                    .put("artist", track.artist)
                    .put("album", track.album)
            )
        }
        return post(
            "/v1/handoff",
            JSONObject()
                .put("tracks", queue)
                .put("start", start)
                .put("position_ms", positionMs.coerceAtLeast(0L))
                .put("autoplay", true),
            timeoutMs = BRIDGE_HANDOFF_TIMEOUT_MS.toInt(),
            readTimeoutMs = BRIDGE_HANDOFF_TIMEOUT_MS.toInt()
        )
    }

    fun stopDesktopSessionIfMatches(tracks: List<Track>, index: Int): JSONObject {
        val queue = JSONArray()
        tracks.forEach { track ->
            queue.put(
                JSONObject()
                    .put("provider_id", track.providerId)
                    .put("track_id", track.trackId)
            )
        }
        return post(
            "/v1/handoff/stop",
            JSONObject().put("expected_queue", queue).put("expected_index", index),
            timeoutMs = BRIDGE_VERIFY_TIMEOUT_MS,
            readTimeoutMs = BRIDGE_VERIFY_TIMEOUT_MS
        )
    }

    fun search(query: String): List<Track> {
        val q = URLEncoder.encode(query, "UTF-8")
        val json = get("/v1/search?q=$q&provider=all")
        return buildList {
            val items = json.optJSONArray("items") ?: return@buildList
            for (index in 0 until items.length()) {
                parseBridgeTrack(items.optJSONObject(index), includeStreamUrl = true)?.let { add(it) }
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
    MaterialTheme(colorScheme = MelodexColorScheme) {
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
    val lifecycleOwner = remember(context) { context as? LifecycleOwner }
    var isAppForeground by remember(lifecycleOwner) {
        mutableStateOf(lifecycleOwner?.lifecycle?.currentState?.isAtLeast(Lifecycle.State.STARTED) == true)
    }
    DisposableEffect(lifecycleOwner) {
        val owner = lifecycleOwner
        if (owner == null) {
            onDispose { }
        } else {
            val observer = LifecycleEventObserver { _, event ->
                when (event) {
                    Lifecycle.Event.ON_START, Lifecycle.Event.ON_RESUME -> isAppForeground = true
                    Lifecycle.Event.ON_STOP, Lifecycle.Event.ON_DESTROY -> isAppForeground = false
                    else -> Unit
                }
            }
            owner.lifecycle.addObserver(observer)
            onDispose { owner.lifecycle.removeObserver(observer) }
        }
    }
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
    var phoneQueue by remember { mutableStateOf<List<Track>>(emptyList()) }
    var queueIndex by remember { mutableStateOf(0) }
    var queueRestored by remember { mutableStateOf(false) }
    var restorePositionMs by remember { mutableStateOf(0L) }
    var queueResolutionRequest by remember { mutableStateOf(0) }
    var queueDialogOpen by remember { mutableStateOf(false) }
    var handoffInProgress by remember { mutableStateOf(false) }
    var suppressQueueRestore by remember { mutableStateOf(false) }
    var bridgeUrl by remember { mutableStateOf("") }
    var token by remember { mutableStateOf("") }
    var manualBridgeUrl by remember { mutableStateOf("") }
    var manualBridgeToken by remember { mutableStateOf("") }
    var bridgeName by remember { mutableStateOf("") }
    var bridgeDeviceId by remember { mutableStateOf("") }
    var bridgeReconnectVersion by remember { mutableStateOf(0) }
    var bridgeConnectionState by remember { mutableStateOf(BridgeConnectionState.UNPAIRED) }
    var showAdvancedBridgeSetup by remember { mutableStateOf(false) }
    var query by remember { mutableStateOf("") }
    var bridgeStatus by remember { mutableStateOf("Pairing is optional. Scan a desktop QR code to connect.") }
    var bridgeResults by remember { mutableStateOf<List<Track>>(emptyList()) }
    var bridgeLibraryStatus by remember { mutableStateOf("Pair a desktop to browse its library. On this phone works without pairing.") }
    var bridgeLibraryLoading by remember { mutableStateOf(false) }
    var desktopPlayback by remember { mutableStateOf<DesktopPlaybackSnapshot?>(null) }
    var desktopPlaybackMessage by remember { mutableStateOf("Pair a computer to view its playback queue.") }
    var desktopPlaybackLoading by remember { mutableStateOf(false) }
    var desktopQueueDialogOpen by remember { mutableStateOf(false) }
    var nowPlaying by remember { mutableStateOf<Track?>(null) }
    var playbackPositionMs by remember { mutableStateOf(0L) }
    var playbackDurationMs by remember { mutableStateOf(0L) }
    var playerIsPlaying by remember { mutableStateOf(player.isPlaying) }

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
                val previousUrl = bridgeUrl
                val previousToken = token
                val previousDeviceId = bridgeDeviceId
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
                    val displayName = pairing.displayName
                    val connected = withContext(Dispatchers.IO) {
                        BridgeClient(pairing.baseUrl, bridgeToken).verify()
                    }
                    if (!connected) throw IllegalStateException("The Bridge did not accept this pairing.")
                    if (previousUrl.isNotBlank() && previousToken.isNotBlank() && previousDeviceId.isNotBlank()) {
                        withContext(Dispatchers.IO) {
                            runCatching {
                                BridgeClient(previousUrl, previousToken).unpair(previousDeviceId, timeoutMs = 1200)
                            }
                        }
                    }
                    withContext(Dispatchers.IO) {
                        BridgeConnectionStore.save(
                            context.applicationContext,
                            StoredBridgeConnection(pairing.baseUrl, bridgeToken, displayName, deviceId)
                        )
                    }
                    bridgeUrl = pairing.baseUrl
                    token = bridgeToken
                    manualBridgeUrl = pairing.baseUrl
                    manualBridgeToken = bridgeToken
                    bridgeName = displayName
                    bridgeDeviceId = deviceId
                    bridgeReconnectVersion += 1
                    bridgeConnectionState = BridgeConnectionState.CONNECTED
                    bridgeResults = emptyList()
                    bridgeLibraryStatus = "Connected. Browse the desktop library or search connected music."
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
        val isCurrentConnection = normalizedUrl == bridgeUrl && normalizedToken == token
        val hasSavedConnection = bridgeUrl.isNotBlank() && token.isNotBlank()
        scope.launch {
            if (isCurrentConnection || !hasSavedConnection) bridgeConnectionState = BridgeConnectionState.CHECKING
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
                manualBridgeUrl = normalizedUrl
                manualBridgeToken = normalizedToken
                bridgeName = displayName
                bridgeDeviceId = deviceId
                bridgeReconnectVersion += 1
                bridgeConnectionState = BridgeConnectionState.CONNECTED
                if (!isCurrentConnection) bridgeResults = emptyList()
                bridgeLibraryStatus = if (bridgeResults.isEmpty()) {
                    "Connected. Browse the desktop library or search connected music."
                } else {
                    "${bridgeResults.size} results are ready."
                }
                bridgeStatus = "Connected to $displayName."
            } catch (e: Exception) {
                if (isCurrentConnection) {
                    bridgeConnectionState = BridgeConnectionState.UNAVAILABLE
                } else if (!hasSavedConnection) {
                    bridgeConnectionState = BridgeConnectionState.UNPAIRED
                }
                if (bridgeConnectionState == BridgeConnectionState.UNAVAILABLE) {
                    bridgeResults = emptyList()
                    bridgeLibraryStatus = "Desktop library unavailable. Switch to On this phone to keep listening."
                } else if (bridgeConnectionState == BridgeConnectionState.UNPAIRED) {
                    bridgeLibraryStatus = "Pair a desktop to browse its library. On this phone works without pairing."
                }
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
            manualBridgeUrl = ""
            manualBridgeToken = ""
            bridgeName = ""
            bridgeDeviceId = ""
            bridgeConnectionState = BridgeConnectionState.UNPAIRED
            bridgeResults = emptyList()
            bridgeLibraryStatus = "Pair a desktop to browse its library. On this phone works without pairing."
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
            manualBridgeUrl = saved.baseUrl
            manualBridgeToken = saved.token
            bridgeName = saved.displayName
            bridgeDeviceId = saved.deviceId
            bridgeConnectionState = BridgeConnectionState.CHECKING
            bridgeStatus = "Checking the saved connection…"
        }
    }

    LaunchedEffect(bridgeUrl, token, isAppForeground) {
        if (bridgeUrl.isBlank() || token.isBlank()) {
            bridgeConnectionState = BridgeConnectionState.UNPAIRED
            bridgeLibraryStatus = "Pair a desktop to browse its library. On this phone works without pairing."
            return@LaunchedEffect
        }
        if (!isAppForeground) return@LaunchedEffect

        while (true) {
            val wasUnavailable = bridgeConnectionState == BridgeConnectionState.UNAVAILABLE
            val wasChecking = bridgeConnectionState == BridgeConnectionState.CHECKING
            try {
                val connected = withContext(Dispatchers.IO) {
                    BridgeClient(bridgeUrl, token).verify()
                }
                if (!connected) throw IllegalStateException("The Bridge did not accept this connection.")
                bridgeConnectionState = BridgeConnectionState.CONNECTED
                if (wasUnavailable) {
                    bridgeReconnectVersion += 1
                    bridgeStatus = "Connection restored to ${bridgeName.ifBlank { "Melodex computer" }}."
                    bridgeLibraryStatus = "Connection restored. Browse the desktop library or search connected music."
                } else if (wasChecking) {
                    bridgeStatus = "Connected to ${bridgeName.ifBlank { "Melodex computer" }}."
                    if (bridgeResults.isEmpty()) {
                        bridgeLibraryStatus = "Connected. Browse the desktop library or search connected music."
                    }
                }
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                bridgeConnectionState = BridgeConnectionState.UNAVAILABLE
                bridgeResults = emptyList()
                bridgeLibraryStatus = "Desktop library unavailable. Switch to On this phone to keep listening."
                bridgeStatus = "Can't reach ${bridgeName.ifBlank { "Melodex computer" }} at its saved LAN address. It may be offline or have a new address. Scan a new QR code to reconnect."
            }
            delay(BRIDGE_CONNECTION_POLL_INTERVAL_MS)
        }
    }

    LaunchedEffect(bridgeUrl, token, bridgeConnectionState, isAppForeground, musicSource) {
        if (musicSource != MusicSource.BRIDGE || !isAppForeground) return@LaunchedEffect
        if (bridgeConnectionState != BridgeConnectionState.CONNECTED) {
            desktopPlayback = null
            desktopQueueDialogOpen = false
            desktopPlaybackLoading = false
            desktopPlaybackMessage = when (bridgeConnectionState) {
                BridgeConnectionState.UNPAIRED -> "Pair a computer to view its playback queue."
                BridgeConnectionState.CHECKING -> "Checking the desktop connection…"
                BridgeConnectionState.UNAVAILABLE -> "Desktop playback is unavailable. Phone playback and its queue still work."
                BridgeConnectionState.CONNECTED -> "Connect to a desktop to view its playback queue."
            }
            return@LaunchedEffect
        }

        while (true) {
            if (!desktopPlaybackLoading) {
                loadDesktopPlayback(showLoading = desktopPlayback == null)
            }
            delay(BRIDGE_CONNECTION_POLL_INTERVAL_MS)
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

    fun searchBridgeLibrary() {
        val searchQuery = query.trim()
        if (searchQuery.isBlank()) {
            bridgeLibraryStatus = "Enter a search to find desktop music."
            return
        }
        if (bridgeConnectionState != BridgeConnectionState.CONNECTED || bridgeLibraryLoading) return
        val baseUrl = bridgeUrl
        val bridgeToken = token
        bridgeLibraryLoading = true
        bridgeLibraryStatus = "Searching connected music…"
        scope.launch {
            try {
                val results = withContext(Dispatchers.IO) {
                    BridgeClient(baseUrl, bridgeToken).search(searchQuery)
                }
                if (baseUrl != bridgeUrl || bridgeToken != token || bridgeConnectionState != BridgeConnectionState.CONNECTED) {
                    return@launch
                }
                bridgeResults = results
                bridgeLibraryStatus = if (results.isEmpty()) {
                    "No matches. Try another search or browse the desktop library."
                } else {
                    "${results.size} results from connected music sources."
                }
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                if (baseUrl == bridgeUrl && bridgeToken == token && bridgeConnectionState == BridgeConnectionState.CONNECTED) {
                    bridgeResults = emptyList()
                    bridgeLibraryStatus = "Search failed. Check the desktop connection and try again."
                }
            } finally {
                bridgeLibraryLoading = false
            }
        }
    }

    fun browseDesktopLibrary() {
        if (bridgeConnectionState != BridgeConnectionState.CONNECTED || bridgeLibraryLoading) return
        val baseUrl = bridgeUrl
        val bridgeToken = token
        bridgeLibraryLoading = true
        bridgeLibraryStatus = "Loading desktop library…"
        scope.launch {
            try {
                val results = withContext(Dispatchers.IO) {
                    BridgeClient(baseUrl, bridgeToken).browse()
                }
                if (baseUrl != bridgeUrl || bridgeToken != token || bridgeConnectionState != BridgeConnectionState.CONNECTED) {
                    return@launch
                }
                bridgeResults = results
                bridgeLibraryStatus = if (results.isEmpty()) {
                    "No desktop tracks found. Check the computer’s local library or search connected music."
                } else {
                    "${results.size} tracks from the desktop library."
                }
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                if (baseUrl == bridgeUrl && bridgeToken == token && bridgeConnectionState == BridgeConnectionState.CONNECTED) {
                    bridgeResults = emptyList()
                    bridgeLibraryStatus = "The desktop library could not be loaded. Reconnect and try again."
                }
            } finally {
                bridgeLibraryLoading = false
            }
        }
    }

    suspend fun loadDesktopPlayback(showLoading: Boolean) {
        if (bridgeConnectionState != BridgeConnectionState.CONNECTED) return
        val baseUrl = bridgeUrl
        val bridgeToken = token
        if (showLoading) {
            desktopPlaybackLoading = true
            desktopPlaybackMessage = if (desktopPlayback == null) "Loading desktop playback…" else "Refreshing desktop playback…"
        }
        try {
            val snapshot = withContext(Dispatchers.IO) {
                BridgeClient(baseUrl, bridgeToken).playbackSnapshot()
            }
            if (baseUrl == bridgeUrl && bridgeToken == token && bridgeConnectionState == BridgeConnectionState.CONNECTED) {
                desktopPlayback = snapshot
                desktopPlaybackMessage = "Desktop playback is up to date."
            }
        } catch (e: CancellationException) {
            throw e
        } catch (_: Exception) {
            if (baseUrl == bridgeUrl && bridgeToken == token && bridgeConnectionState == BridgeConnectionState.CONNECTED) {
                desktopPlayback = null
                desktopQueueDialogOpen = false
                desktopPlaybackMessage = "Desktop playback status could not be loaded. Reconnect or refresh to try again."
            }
        } finally {
            if (showLoading) desktopPlaybackLoading = false
        }
    }

    fun refreshDesktopPlayback() {
        if (bridgeConnectionState != BridgeConnectionState.CONNECTED || desktopPlaybackLoading) return
        scope.launch { loadDesktopPlayback(showLoading = true) }
    }

    fun savePhoneQueue(tracks: List<Track>, index: Int, positionMs: Long) {
        if (tracks.isEmpty()) {
            LocalQueueStore.clearAsync(context)
            return
        }
        LocalQueueStore.saveAsync(
            context,
            tracks,
            index.coerceIn(0, tracks.lastIndex),
            positionMs.coerceAtLeast(0L)
        )
    }

    fun playQueueTrack(index: Int, positionMs: Long = 0L, autoplay: Boolean = true) {
        val queued = phoneQueue.getOrNull(index) ?: return
        queueResolutionRequest += 1
        val requestId = queueResolutionRequest
        val targetPositionMs = positionMs.coerceAtLeast(0L)
        queueIndex = index
        restorePositionMs = targetPositionMs
        savePhoneQueue(phoneQueue, index, targetPositionMs)

        if (queued.source == TrackSource.PHONE) {
            if (!autoplay) player.pause()
            nowPlaying = queued
            player.setMediaItem(trackToMediaItem(queued), targetPositionMs)
            player.prepare()
            if (autoplay) player.play() else player.pause()
            return
        }

        player.pause()
        player.clearMediaItems()
        nowPlaying = null
        val baseUrl = bridgeUrl
        val bridgeToken = token
        if (baseUrl.isBlank() || bridgeToken.isBlank()) {
            bridgeStatus = "Connect to the Bridge to play this queued track."
            return
        }
        bridgeStatus = "Resolving ${queued.title}…"
        scope.launch {
            try {
                val resolved = withContext(Dispatchers.IO) {
                    BridgeClient(baseUrl, bridgeToken).resolve(queued)
                }
                if (requestId != queueResolutionRequest) return@launch
                if (resolved.streamUrl.isBlank()) {
                    throw IllegalStateException("Source did not return a stream URL")
                }
                val resolvedIndex = phoneQueue.indexOfFirst { it.queueKey() == queued.queueKey() }
                if (resolvedIndex < 0) return@launch
                queueIndex = resolvedIndex
                nowPlaying = resolved
                player.setMediaItem(trackToMediaItem(resolved), targetPositionMs)
                player.prepare()
                if (autoplay) player.play() else player.pause()
                bridgeStatus = if (autoplay) "Playing on this phone." else "Bridge track ready."
            } catch (e: Exception) {
                if (requestId == queueResolutionRequest) {
                    bridgeStatus = e.message ?: "Playback failed."
                }
            }
        }
    }

    fun startLocalQueue(track: Track, candidates: List<Track>) {
        val queue = if (candidates.any { it.queueKey() == track.queueKey() }) candidates else listOf(track)
        val startIndex = queue.indexOfFirst { it.queueKey() == track.queueKey() }.coerceAtLeast(0)
        phoneQueue = queue
        queueIndex = startIndex
        nowPlaying = track
        savePhoneQueue(queue, startIndex, 0L)
        playQueueTrack(startIndex, 0L, true)
    }

    fun startBridgeQueue(track: Track) {
        phoneQueue = listOf(track.copy(streamUrl = ""))
        queueIndex = 0
        playQueueTrack(0, 0L, true)
    }

    fun addToPhoneQueue(track: Track) {
        if (phoneQueue.any { it.queueKey() == track.queueKey() }) {
            if (track.source == TrackSource.PHONE) {
                localStatus = "That track is already in the queue."
            } else {
                bridgeStatus = "That track is already in the queue."
            }
            return
        }
        val stableTrack = if (track.source == TrackSource.BRIDGE) track.copy(streamUrl = "") else track
        val updatedQueue = phoneQueue + stableTrack
        phoneQueue = updatedQueue
        if (updatedQueue.size == 1) {
            queueIndex = 0
            savePhoneQueue(updatedQueue, 0, 0L)
            playQueueTrack(0, 0L, true)
        } else {
            val positionMs = if (player.currentMediaItem != null) {
                player.currentPosition.coerceAtLeast(0L)
            } else {
                restorePositionMs
            }
            queueIndex = queueIndex.coerceIn(0, updatedQueue.lastIndex)
            savePhoneQueue(updatedQueue, queueIndex, positionMs)
        }
        if (track.source == TrackSource.PHONE) {
            localStatus = "Added to queue: ${track.title}"
        } else {
            bridgeStatus = "Added to queue: ${track.title}"
        }
    }

    fun removeFromPhoneQueue(index: Int) {
        if (index !in phoneQueue.indices) return
        val currentKey = phoneQueue.getOrNull(queueIndex)?.queueKey()
        val removingCurrent = phoneQueue[index].queueKey() == currentKey
        val wasPlaying = player.isPlaying
        val updatedQueue = phoneQueue.toMutableList().also { it.removeAt(index) }
        queueResolutionRequest += 1
        if (updatedQueue.isEmpty()) {
            phoneQueue = emptyList()
            queueIndex = 0
            restorePositionMs = 0L
            nowPlaying = null
            player.clearMediaItems()
            LocalQueueStore.clearAsync(context)
            return
        }
        phoneQueue = updatedQueue
        val nextIndex = updatedQueue.indexOfFirst { it.queueKey() == currentKey }
            .takeIf { it >= 0 }
            ?: index.coerceIn(0, updatedQueue.lastIndex)
        queueIndex = nextIndex
        if (removingCurrent) {
            playQueueTrack(nextIndex, 0L, wasPlaying)
        } else {
            val positionMs = if (player.currentMediaItem != null) {
                player.currentPosition.coerceAtLeast(0L)
            } else {
                restorePositionMs
            }
            savePhoneQueue(updatedQueue, nextIndex, positionMs)
        }
    }

    fun moveQueueItem(fromIndex: Int, toIndex: Int) {
        if (fromIndex !in phoneQueue.indices || toIndex !in phoneQueue.indices || fromIndex == toIndex) return
        val currentKey = phoneQueue.getOrNull(queueIndex)?.queueKey()
        val updatedQueue = phoneQueue.toMutableList().also { tracks ->
            val moved = tracks.removeAt(fromIndex)
            tracks.add(toIndex, moved)
        }
        phoneQueue = updatedQueue
        queueIndex = updatedQueue.indexOfFirst { it.queueKey() == currentKey }.coerceAtLeast(0)
        val positionMs = if (player.currentMediaItem != null) {
            player.currentPosition.coerceAtLeast(0L)
        } else {
            restorePositionMs
        }
        savePhoneQueue(updatedQueue, queueIndex, positionMs)
    }

    fun clearPhoneQueue() {
        queueResolutionRequest += 1
        player.clearMediaItems()
        nowPlaying = null
        phoneQueue = emptyList()
        queueIndex = 0
        restorePositionMs = 0L
        LocalQueueStore.clearAsync(context)
        queueDialogOpen = false
    }

    fun moveDesktopPlaybackToPhone() {
        if (handoffInProgress || bridgeConnectionState != BridgeConnectionState.CONNECTED) return
        scope.launch {
            handoffInProgress = true
            suppressQueueRestore = true
            bridgeStatus = "Checking the desktop queue…"
            try {
                val baseUrl = bridgeUrl
                val bridgeToken = token
                val desktopStatus = withContext(Dispatchers.IO) {
                    BridgeClient(baseUrl, bridgeToken).status()
                }
                val desktopQueue = mutableListOf<Track>()
                val queueJson = desktopStatus.optJSONArray("queue")
                if (queueJson != null) {
                    for (index in 0 until queueJson.length()) {
                        val item = queueJson.optJSONObject(index)
                        if (item == null) {
                            bridgeStatus = "The desktop queue could not be read safely."
                            return@launch
                        }
                        desktopQueue += Track(
                            providerId = item.optString("provider_id"),
                            trackId = item.optString("track_id"),
                            title = item.optString("title", "Unknown track"),
                            artist = item.optString("artist", "Unknown artist"),
                            album = item.optString("album"),
                            durationMs = item.optLong("duration_ms", 0L).coerceAtLeast(0L),
                            source = TrackSource.BRIDGE
                        )
                    }
                }
                if (desktopQueue.isEmpty()) {
                    val current = desktopStatus.optJSONObject("current_track")
                    if (current != null) {
                        desktopQueue += Track(
                            providerId = current.optString("provider_id"),
                            trackId = current.optString("track_id"),
                            title = current.optString("title", "Unknown track"),
                            artist = current.optString("artist", "Unknown artist"),
                            album = current.optString("album"),
                            durationMs = current.optLong("duration_ms", 0L).coerceAtLeast(0L),
                            source = TrackSource.BRIDGE
                        )
                    }
                }
                if (desktopQueue.isEmpty()) {
                    bridgeStatus = "There is no desktop playback queue to move."
                    return@launch
                }
                if (desktopQueue.any { it.providerId.isBlank() || it.trackId.isBlank() }) {
                    bridgeStatus = "The desktop queue has a track without a stable Bridge identity."
                    return@launch
                }
                val desktopIndex = desktopStatus.optInt("index", 0)
                val start = if (desktopIndex < 0 && desktopQueue.size == 1) 0 else desktopIndex
                if (start !in desktopQueue.indices) {
                    bridgeStatus = "The desktop has no current queue position to move."
                    return@launch
                }
                val desktopWasPlaying = desktopStatus.optBoolean("playing", false)
                val positionMs = desktopStatus.optLong("position_ms", 0L).coerceAtLeast(0L)
                val previousQueue = phoneQueue
                val previousIndex = queueIndex
                val previousPositionMs = if (player.currentMediaItem != null) {
                    player.currentPosition.coerceAtLeast(0L)
                } else {
                    restorePositionMs
                }
                val previousWasPlaying = player.isPlaying
                val transferKeys = desktopQueue.map { it.queueKey() }
                phoneQueue = desktopQueue
                queueIndex = start
                bridgeStatus = if (desktopWasPlaying) {
                    "Starting the desktop session on this phone…"
                } else {
                    "Loading the paused desktop queue on this phone…"
                }
                playQueueTrack(start, positionMs, desktopWasPlaying)
                val phoneReady = withTimeoutOrNull(BRIDGE_HANDOFF_TIMEOUT_MS) {
                    while (true) {
                        val playbackReady = if (desktopWasPlaying) {
                            player.isPlaying
                        } else {
                            player.playbackState == Player.STATE_READY
                        }
                        if (
                            phoneQueue.map { it.queueKey() } == transferKeys &&
                            nowPlaying?.queueKey() == desktopQueue[start].queueKey() &&
                            player.currentMediaItem?.mediaId == desktopQueue[start].queueKey() &&
                            playbackReady
                        ) {
                            return@withTimeoutOrNull true
                        }
                        delay(BRIDGE_HANDOFF_POLL_INTERVAL_MS)
                    }
                    false
                } ?: false
                if (!phoneReady) {
                    if (phoneQueue.map { it.queueKey() } == transferKeys) {
                        phoneQueue = previousQueue
                        queueIndex = previousIndex
                        restorePositionMs = previousPositionMs
                        if (previousQueue.isNotEmpty()) {
                            val previousStart = previousIndex.coerceIn(previousQueue.indices)
                            val previousTrack = previousQueue[previousStart]
                            playQueueTrack(previousStart, previousPositionMs, previousWasPlaying)
                            withTimeoutOrNull(BRIDGE_HANDOFF_TIMEOUT_MS) {
                                while (true) {
                                    val playbackReady = if (previousWasPlaying) {
                                        player.isPlaying
                                    } else {
                                        player.playbackState == Player.STATE_READY
                                    }
                                    if (
                                        nowPlaying?.queueKey() == previousTrack.queueKey() &&
                                        player.currentMediaItem?.mediaId == previousTrack.queueKey() &&
                                        playbackReady
                                    ) return@withTimeoutOrNull true
                                    delay(BRIDGE_HANDOFF_POLL_INTERVAL_MS)
                                }
                                false
                            }
                        } else {
                            player.clearMediaItems()
                            nowPlaying = null
                        }
                    }
                    bridgeStatus = "This phone couldn't start the desktop session, so desktop playback was left alone."
                    return@launch
                }
                if (desktopWasPlaying && phoneQueue.map { it.queueKey() } == transferKeys) {
                    val stopped = withContext(Dispatchers.IO) {
                        BridgeClient(baseUrl, bridgeToken).stopDesktopSessionIfMatches(desktopQueue, start)
                    }
                    bridgeStatus = when {
                        stopped.optBoolean("stopped") -> "Moved desktop playback to this phone."
                        stopped.optString("reason") == "desktop_session_changed" ->
                            "Playing this session here; the desktop changed sessions, so it was left alone."
                        else -> "Playing here. The desktop was already stopped."
                    }
                } else {
                    bridgeStatus = "Loaded the desktop queue on this phone, paused."
                }
            } catch (e: Exception) {
                bridgeStatus = e.message ?: "Playback handoff failed."
            } finally {
                suppressQueueRestore = false
                handoffInProgress = false
            }
        }
    }

    fun movePhoneQueueToDesktop() {
        if (
            handoffInProgress ||
            bridgeConnectionState != BridgeConnectionState.CONNECTED ||
            !player.isPlaying ||
            phoneQueue.isEmpty() ||
            phoneQueue.any {
                it.source != TrackSource.BRIDGE || it.providerId.isBlank() || it.trackId.isBlank()
            }
        ) return
        scope.launch {
            handoffInProgress = true
            val baseUrl = bridgeUrl
            val bridgeToken = token
            val transferQueue = phoneQueue.toList()
            val start = queueIndex.coerceIn(transferQueue.indices)
            val positionMs = player.currentPosition.coerceAtLeast(0L)
            var handoffAccepted = false
            bridgeStatus = "Sending this phone queue to the desktop…"
            try {
                val accepted = withContext(Dispatchers.IO) {
                    BridgeClient(baseUrl, bridgeToken).handoffToDesktop(transferQueue, start, positionMs)
                }
                if (!accepted.optBoolean("ok")) {
                    bridgeStatus = "The desktop refused this handoff."
                    return@launch
                }
                handoffAccepted = true
                val desktopStarted = withTimeoutOrNull(BRIDGE_HANDOFF_TIMEOUT_MS) {
                    while (true) {
                        val status = withContext(Dispatchers.IO) {
                            BridgeClient(baseUrl, bridgeToken).status()
                        }
                        if (status.matchesBridgeQueue(transferQueue, start) && status.optBoolean("playing")) {
                            return@withTimeoutOrNull true
                        }
                        delay(BRIDGE_HANDOFF_POLL_INTERVAL_MS)
                    }
                    false
                } ?: false
                if (!desktopStarted) {
                    var desktopStopped = false
                    try {
                        desktopStopped = withContext(Dispatchers.IO) {
                            BridgeClient(baseUrl, bridgeToken)
                                .stopDesktopSessionIfMatches(transferQueue, start)
                                .optBoolean("stopped")
                        }
                    } catch (_: Exception) {
                        // Keep the phone queue playing if the guarded stop cannot be confirmed.
                    }
                    bridgeStatus = if (desktopStopped) {
                        "The desktop did not start; this phone kept playing the queue."
                    } else {
                        "Could not confirm desktop playback. This phone kept playing."
                    }
                    return@launch
                }
                val phoneSessionStillMatches =
                    player.isPlaying &&
                        phoneQueue.map { it.queueKey() } == transferQueue.map { it.queueKey() } &&
                        queueIndex == start &&
                        player.currentMediaItem?.mediaId == transferQueue[start].queueKey()
                if (phoneSessionStillMatches) {
                    player.pause()
                    clearPhoneQueue()
                    bridgeStatus = "Moved playback to ${bridgeName.ifBlank { "the desktop" }}."
                } else {
                    try {
                        withContext(Dispatchers.IO) {
                            BridgeClient(baseUrl, bridgeToken)
                                .stopDesktopSessionIfMatches(transferQueue, start)
                        }
                    } catch (_: Exception) {
                        // The phone session changed; keep the phone's current state.
                    }
                    bridgeStatus = "The phone session changed during handoff, so it was left alone."
                }
            } catch (e: Exception) {
                if (handoffAccepted) {
                    try {
                        withContext(Dispatchers.IO) {
                            BridgeClient(baseUrl, bridgeToken).stopDesktopSessionIfMatches(transferQueue, start)
                        }
                    } catch (_: Exception) {
                        // The request may be unavailable; its queue identity guard protects any retry.
                    }
                }
                bridgeStatus = e.message ?: "Playback handoff failed. This phone kept playing."
            } finally {
                handoffInProgress = false
            }
        }
    }

    fun playNextQueueTrack() {
        if (queueIndex + 1 < phoneQueue.size) {
            playQueueTrack(queueIndex + 1, 0L, true)
        }
    }

    fun playPreviousQueueTrack() {
        if (queueIndex > 0) {
            playQueueTrack(queueIndex - 1, 0L, true)
        } else if (player.mediaItemCount > 0) {
            player.seekTo(0L)
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

    LaunchedEffect(player) {
        val savedQueue = withContext(Dispatchers.IO) { LocalQueueStore.load(context) }
        if (savedQueue != null) {
            phoneQueue = savedQueue.tracks
            queueIndex = savedQueue.currentIndex
            restorePositionMs = savedQueue.currentPositionMs
            val restoredTrack = savedQueue.tracks.getOrNull(savedQueue.currentIndex)
            if (restoredTrack?.source == TrackSource.PHONE) nowPlaying = restoredTrack
        }
        queueRestored = true
    }

    LaunchedEffect(player, queueRestored, hasAudioPermission, bridgeUrl, token, bridgeReconnectVersion, phoneQueue, queueIndex, suppressQueueRestore) {
        if (suppressQueueRestore || !queueRestored || phoneQueue.isEmpty() || player.mediaItemCount > 0) return@LaunchedEffect
        val queued = phoneQueue.getOrNull(queueIndex) ?: return@LaunchedEffect
        if (queued.source == TrackSource.PHONE) {
            if (!hasAudioPermission) return@LaunchedEffect
            val durationMs = queued.durationMs
            val positionMs = if (durationMs > 0L) {
                restorePositionMs.coerceAtMost((durationMs - 1_000L).coerceAtLeast(0L))
            } else {
                restorePositionMs
            }
            player.setMediaItem(trackToMediaItem(queued), positionMs)
            player.prepare()
        } else if (bridgeUrl.isNotBlank() && token.isNotBlank()) {
            playQueueTrack(queueIndex, restorePositionMs, false)
        }
    }

    val latestQueue = rememberUpdatedState(phoneQueue)
    val latestQueueIndex = rememberUpdatedState(queueIndex)
    val latestPlayQueueTrack = rememberUpdatedState<(Int, Long, Boolean) -> Unit>(
        { index, positionMs, autoplay -> playQueueTrack(index, positionMs, autoplay) }
    )
    LaunchedEffect(player) {
        while (true) {
            playbackPositionMs = player.currentPosition.coerceAtLeast(0L)
            playbackDurationMs = player.duration.takeIf { it > 0L } ?: 0L
            playerIsPlaying = player.isPlaying
            delay(500L)
        }
    }
    DisposableEffect(player) {
        val listener = object : Player.Listener {
            override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) {
                if (mediaItem == null) {
                    nowPlaying = null
                    return
                }
                val index = latestQueue.value.indexOfFirst { it.queueKey() == mediaItem.mediaId }
                if (index >= 0) {
                    queueIndex = index
                    nowPlaying = latestQueue.value[index]
                }
            }

            override fun onPlaybackStateChanged(playbackState: Int) {
                if (playbackState == Player.STATE_ENDED) {
                    val nextIndex = latestQueueIndex.value + 1
                    if (nextIndex < latestQueue.value.size) {
                        latestPlayQueueTrack.value(nextIndex, 0L, true)
                    }
                }
            }

            override fun onIsPlayingChanged(isPlaying: Boolean) {
                playerIsPlaying = isPlaying
            }
        }
        player.addListener(listener)
        onDispose { player.removeListener(listener) }
    }

    MaterialTheme(colorScheme = MelodexColorScheme) {
        Scaffold(
            topBar = {
                TopAppBar(
                    title = {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Box(
                                Modifier.size(36.dp)
                                    .clip(CircleShape)
                                    .background(MaterialTheme.colorScheme.surfaceVariant),
                                contentAlignment = Alignment.Center
                            ) {
                                Text("♫", color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.titleLarge)
                            }
                            Spacer(Modifier.width(10.dp))
                            Column(verticalArrangement = Arrangement.spacedBy(0.dp)) {
                                Text("Melodex", style = MaterialTheme.typography.titleMedium)
                                Text(
                                    "YOUR MUSIC, IN REACH",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                        }
                    },
                    actions = {
                        val context = LocalContext.current
                        TextButton(
                            onClick = {
                                context.startActivity(
                                    Intent(Intent.ACTION_VIEW, Uri.parse(PRIVACY_POLICY_URL))
                                )
                            }
                        ) {
                            Text("Privacy policy")
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = MaterialTheme.colorScheme.background
                    )
                )
            }
        ) { pad ->
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
                    if (musicSource == MusicSource.PHONE) "Play from this phone" else "Browse and play from your Melodex Bridge",
                    style = MaterialTheme.typography.titleMedium
                )
                Text(
                    "Playback and controls stay on this phone.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
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
                                    enabled = phoneQueue.isNotEmpty()
                                ) { Text("Queue (${phoneQueue.size})") }
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
                                        onAddToQueue = ::addToPhoneQueue,
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
                        Card(Modifier.fillMaxWidth()) {
                            Column(
                                Modifier.fillMaxWidth().padding(16.dp),
                                verticalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                if (bridgeUrl.isNotBlank() && token.isNotBlank()) {
                                    Text(
                                        "Paired with ${bridgeName.ifBlank { "Melodex computer" }}",
                                        style = MaterialTheme.typography.titleSmall
                                    )
                                    Text(
                                        when (bridgeConnectionState) {
                                            BridgeConnectionState.UNPAIRED -> "Not paired"
                                            BridgeConnectionState.CHECKING -> "Checking connection…"
                                            BridgeConnectionState.CONNECTED -> "Connected"
                                            BridgeConnectionState.UNAVAILABLE -> "Desktop unavailable"
                                        },
                                        style = MaterialTheme.typography.titleSmall
                                    )
                                    Text(
                                        if (bridgeConnectionState == BridgeConnectionState.UNAVAILABLE) {
                                            "The computer may be offline or have a new address. Scan a new QR code to reconnect."
                                        } else {
                                            "This phone has its own player. Pair another phone separately to listen independently."
                                        },
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                    Text(bridgeStatus, style = MaterialTheme.typography.bodySmall)
                                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                        Button(onClick = {
                                            connectBridge(bridgeUrl, token, bridgeName, bridgeDeviceId)
                                        }) { Text("Reconnect") }
                                        OutlinedButton(onClick = { startQrScan() }) { Text("Scan new QR code") }
                                    }
                                    OutlinedButton(
                                        onClick = { moveDesktopPlaybackToPhone() },
                                        enabled = bridgeConnectionState == BridgeConnectionState.CONNECTED && !handoffInProgress,
                                        modifier = Modifier.fillMaxWidth()
                                    ) {
                                        Text(if (handoffInProgress) "Moving playback…" else "Move desktop playback to this phone")
                                    }
                                    TextButton(onClick = { forgetBridge() }) { Text("Forget on this phone") }
                                } else {
                                    Text(
                                        "Pair this phone over local Wi-Fi. Each phone keeps its own player, so listening here will not interrupt another phone."
                                    )
                                    Button(
                                        onClick = { startQrScan() },
                                        modifier = Modifier.fillMaxWidth()
                                    ) { Text("Scan desktop QR code") }
                                    Text(bridgeStatus, style = MaterialTheme.typography.bodySmall)
                                }

                                TextButton(onClick = { showAdvancedBridgeSetup = !showAdvancedBridgeSetup }) {
                                    Text(if (showAdvancedBridgeSetup) "Hide advanced setup" else "Advanced setup")
                                }
                                if (showAdvancedBridgeSetup) {
                                    OutlinedTextField(
                                        manualBridgeUrl,
                                        { manualBridgeUrl = it },
                                        label = { Text("Bridge URL") },
                                        placeholder = { Text("http://192.168.1.20:8766") },
                                        singleLine = true,
                                        modifier = Modifier.fillMaxWidth()
                                    )
                                    OutlinedTextField(
                                        manualBridgeToken,
                                        { manualBridgeToken = it },
                                        label = { Text("Bridge token") },
                                        visualTransformation = PasswordVisualTransformation(),
                                        singleLine = true,
                                        modifier = Modifier.fillMaxWidth()
                                    )
                                    Button(onClick = {
                                        connectBridge(manualBridgeUrl, manualBridgeToken)
                                    }) { Text("Connect manually") }
                                }
                            }
                        }

                        if (bridgeUrl.isNotBlank() && token.isNotBlank()) {
                            Card(Modifier.fillMaxWidth()) {
                                Column(
                                    Modifier.fillMaxWidth().padding(16.dp),
                                    verticalArrangement = Arrangement.spacedBy(6.dp)
                                ) {
                                    Text("Desktop playback", style = MaterialTheme.typography.titleSmall)
                                    val snapshot = desktopPlayback
                                    if (snapshot == null) {
                                        Text(
                                            desktopPlaybackMessage,
                                            style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant
                                        )
                                        if (desktopPlaybackLoading) {
                                            CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                                        }
                                        OutlinedButton(
                                            onClick = { refreshDesktopPlayback() },
                                            enabled = bridgeConnectionState == BridgeConnectionState.CONNECTED &&
                                                !desktopPlaybackLoading
                                        ) {
                                            Text(if (desktopPlaybackLoading) "Refreshing…" else "Refresh status")
                                        }
                                    } else {
                                        val currentTrack = snapshot.currentTrack
                                        Text(
                                            when {
                                                currentTrack == null -> "Nothing is playing on the desktop."
                                                snapshot.isPlaying -> "Playing on the desktop"
                                                else -> "Paused on the desktop"
                                            },
                                            style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant
                                        )
                                        if (currentTrack != null) {
                                            Text(
                                                "${currentTrack.title} · ${currentTrack.artist}",
                                                style = MaterialTheme.typography.bodyMedium,
                                                maxLines = 1,
                                                overflow = TextOverflow.Ellipsis
                                            )
                                        }
                                        Text(
                                            "Queue: ${snapshot.queue.size} tracks · Position ${snapshot.positionMs / 1000}s",
                                            style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant
                                        )
                                        Text(
                                            desktopPlaybackMessage,
                                            style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant
                                        )
                                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                            OutlinedButton(
                                                onClick = { refreshDesktopPlayback() },
                                                enabled = bridgeConnectionState == BridgeConnectionState.CONNECTED &&
                                                    !desktopPlaybackLoading
                                            ) {
                                                Text(if (desktopPlaybackLoading) "Refreshing…" else "Refresh")
                                            }
                                            TextButton(
                                                onClick = { desktopQueueDialogOpen = true }
                                            ) { Text("View queue (${snapshot.queue.size})") }
                                        }
                                    }
                                }
                            }
                        }

                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                            OutlinedTextField(
                                query,
                                { query = it },
                                label = { Text("Search desktop music") },
                                singleLine = true,
                                modifier = Modifier.weight(1f)
                            )
                            Button(
                                onClick = { searchBridgeLibrary() },
                                enabled = bridgeConnectionState == BridgeConnectionState.CONNECTED &&
                                    query.isNotBlank() && !bridgeLibraryLoading
                            ) { Text("Search") }
                        }
                        OutlinedButton(
                            onClick = { browseDesktopLibrary() },
                            enabled = bridgeConnectionState == BridgeConnectionState.CONNECTED && !bridgeLibraryLoading,
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text(if (bridgeLibraryLoading) "Loading…" else "Browse desktop library")
                        }
                        Text(
                            bridgeLibraryStatus,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        if (phoneQueue.isNotEmpty()) {
                            OutlinedButton(
                                onClick = { queueDialogOpen = true },
                                modifier = Modifier.fillMaxWidth()
                            ) { Text("Queue (${phoneQueue.size})") }
                        }
                        TrackList(
                            bridgeResults,
                            onSelect = ::startBridgeQueue,
                            onAddToQueue = ::addToPhoneQueue,
                            showQueueAction = true,
                            modifier = Modifier.weight(1f)
                        )
                    }
                }

                nowPlaying?.let { track ->
                    NowPlayingCard(
                        track = track,
                        isPlaying = playerIsPlaying,
                        positionMs = playbackPositionMs,
                        durationMs = playbackDurationMs,
                        queueCount = phoneQueue.size.takeIf { it > 0 },
                        onPrevious = ::playPreviousQueueTrack,
                        onNext = ::playNextQueueTrack,
                        onPlayPause = { if (player.isPlaying) player.pause() else player.play() },
                        onRestart = { player.seekTo(0L) },
                        onSeek = { player.seekTo(it) },
                        onQueue = { queueDialogOpen = true },
                        onMoveToDesktop = if (
                            bridgeConnectionState == BridgeConnectionState.CONNECTED &&
                            !handoffInProgress &&
                            playerIsPlaying &&
                            phoneQueue.isNotEmpty() &&
                            phoneQueue.all {
                                it.source == TrackSource.BRIDGE &&
                                    it.providerId.isNotBlank() &&
                                    it.trackId.isNotBlank()
                            }
                        ) {
                            { movePhoneQueueToDesktop() }
                        } else {
                            null
                        }
                    )
                }
            }
        }

        if (desktopQueueDialogOpen) {
            val snapshot = desktopPlayback
            if (snapshot != null) {
                AlertDialog(
                    onDismissRequest = { desktopQueueDialogOpen = false },
                    title = { Text("Desktop queue (${snapshot.queue.size})") },
                    text = {
                        if (snapshot.queue.isEmpty()) {
                            Text("The desktop queue is empty.")
                        } else {
                            LazyColumn(Modifier.heightIn(max = 420.dp)) {
                                itemsIndexed(snapshot.queue, key = { index, track -> "${track.queueKey()}|$index" }) { index, track ->
                                    val selected = index == snapshot.currentIndex
                                    ListItem(
                                        headlineContent = { Text(track.title) },
                                        supportingContent = {
                                            Text(
                                                if (selected && snapshot.isPlaying) "Playing on desktop · ${track.artist}"
                                                else if (selected) "Selected on desktop · ${track.artist}"
                                                else track.artist
                                            )
                                        },
                                        trailingContent = {
                                            Text("${index + 1}", color = MaterialTheme.colorScheme.onSurfaceVariant)
                                        }
                                    )
                                }
                            }
                        }
                    },
                    confirmButton = {
                        TextButton(onClick = { desktopQueueDialogOpen = false }) { Text("Close") }
                    }
                )
            }
        }

        if (queueDialogOpen) {
            AlertDialog(
                onDismissRequest = { queueDialogOpen = false },
                title = { Text("Play queue (${phoneQueue.size})") },
                text = {
                    if (phoneQueue.isEmpty()) {
                        Text("Add local or Bridge tracks to this phone’s queue.")
                    } else {
                        LazyColumn(Modifier.heightIn(max = 420.dp)) {
                            itemsIndexed(phoneQueue, key = { _, track -> track.queueKey() }) { index, track ->
                                val sourceLabel = if (track.source == TrackSource.BRIDGE) {
                                    "Bridge · ${track.providerId}"
                                } else {
                                    "On this phone"
                                }
                                ListItem(
                                    leadingContent = { TrackArtwork(track, Modifier.size(48.dp)) },
                                    headlineContent = { Text(track.title) },
                                    supportingContent = { Text("$sourceLabel · ${track.artist}${if (track.album.isNotBlank()) " · ${track.album}" else ""}") },
                                    trailingContent = {
                                        Row {
                                            TextButton(
                                                enabled = index > 0,
                                                onClick = { moveQueueItem(index, index - 1) }
                                            ) { Text("↑") }
                                            TextButton(
                                                enabled = index < phoneQueue.lastIndex,
                                                onClick = { moveQueueItem(index, index + 1) }
                                            ) { Text("↓") }
                                            TextButton(onClick = { removeFromPhoneQueue(index) }) { Text("Remove") }
                                        }
                                    },
                                    modifier = Modifier.clickable {
                                        playQueueTrack(index, 0L, true)
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
                    if (phoneQueue.isNotEmpty()) {
                        TextButton(onClick = ::clearPhoneQueue) { Text("Clear queue") }
                    }
                }
            )
        }
    }
}

@Composable
private fun NowPlayingCard(
    track: Track,
    isPlaying: Boolean,
    positionMs: Long,
    durationMs: Long,
    queueCount: Int?,
    onPrevious: () -> Unit,
    onNext: () -> Unit,
    onPlayPause: () -> Unit,
    onRestart: () -> Unit,
    onSeek: (Long) -> Unit,
    onQueue: () -> Unit,
    onMoveToDesktop: (() -> Unit)? = null
) {
    val duration = durationMs.takeIf { it > 0L } ?: track.durationMs
    var isSeeking by remember(track.source, track.providerId, track.trackId) { mutableStateOf(false) }
    var seekFraction by remember(track.source, track.providerId, track.trackId) { mutableStateOf(0f) }
    val playbackFraction = if (duration > 0L) {
        (positionMs.toFloat() / duration.toFloat()).coerceIn(0f, 1f)
    } else {
        0f
    }
    val shownFraction = if (isSeeking) seekFraction else playbackFraction

    Card(
        Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Column(
            Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 10.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                TrackArtwork(track, Modifier.size(56.dp))
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(
                        "NOW PLAYING",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.primary
                    )
                    Text(
                        track.title.ifBlank { "Unknown track" },
                        style = MaterialTheme.typography.titleSmall,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    Text(
                        track.artist.ifBlank { "Unknown artist" },
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }

            if (duration > 0L) {
                Slider(
                    value = shownFraction,
                    onValueChange = {
                        seekFraction = it
                        isSeeking = true
                    },
                    onValueChangeFinished = {
                        if (isSeeking) onSeek((seekFraction * duration).roundToLong())
                        isSeeking = false
                    },
                    valueRange = 0f..1f,
                    modifier = Modifier.fillMaxWidth()
                )
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    val shownPosition = if (isSeeking) (seekFraction * duration).roundToLong() else positionMs
                    Text(formatDuration(shownPosition), style = MaterialTheme.typography.labelSmall)
                    Text(formatDuration(duration), style = MaterialTheme.typography.labelSmall)
                }
            }

            Row(verticalAlignment = Alignment.CenterVertically) {
                TextButton(onClick = onPrevious) { Text("Prev") }
                TextButton(onClick = onRestart) { Text("Restart") }
                TextButton(onClick = onNext) { Text("Next") }
                Spacer(Modifier.weight(1f))
                if (queueCount != null) {
                    TextButton(onClick = onQueue) { Text("Queue ($queueCount)") }
                }
                Button(onClick = onPlayPause) {
                    Text(if (isPlaying) "Pause" else "Play")
                }
            }
            onMoveToDesktop?.let { action ->
                OutlinedButton(
                    onClick = action,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("Move this queue to desktop")
                }
            }
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
    val bitmap by produceState<Bitmap?>(initialValue = null, key1 = track.queueKey(), key2 = track.streamUrl) {
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
        .setMediaId(track.queueKey())
        .setUri(track.streamUrl)
        .setMediaMetadata(metadata)
        .build()
}

private fun formatDuration(durationMs: Long): String {
    if (durationMs <= 0L) return ""
    val seconds = durationMs / 1000L
    return "${seconds / 60}:${(seconds % 60).toString().padStart(2, '0')}"
}

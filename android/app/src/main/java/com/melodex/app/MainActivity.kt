package com.melodex.app

import android.Manifest
import android.content.ComponentName
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.Player
import androidx.media3.session.MediaController
import androidx.media3.session.SessionToken
import coil.compose.AsyncImage
import com.google.common.util.concurrent.ListenableFuture
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

private enum class AppTab { MUSIC, CONNECT }

class MainActivity : ComponentActivity() {
    private var mediaController by mutableStateOf<MediaController?>(null)
    private var controllerFuture: ListenableFuture<MediaController>? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val token = SessionToken(this, ComponentName(this, MelodexPlaybackService::class.java))
        val future = MediaController.Builder(this, token).buildAsync()
        controllerFuture = future
        future.addListener({
            runCatching { future.get() }.onSuccess { mediaController = it }
        }, { command -> command.run() })
        setContent { MelodexApp(mediaController) }
    }

    override fun onDestroy() {
        mediaController = null
        controllerFuture?.let { MediaController.releaseFuture(it) }
        controllerFuture = null
        super.onDestroy()
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun MelodexApp(player: MediaController?) {
    val context = LocalContext.current
    val prefs = remember { context.getSharedPreferences("melodex_mobile", Context.MODE_PRIVATE) }
    val likedIds = remember {
        mutableStateListOf<String>().apply {
            addAll(prefs.getStringSet("liked_tracks", emptySet()).orEmpty())
        }
    }
    var selectedTab by remember { mutableStateOf(AppTab.MUSIC) }
    var tracks by remember { mutableStateOf<List<Track>>(emptyList()) }
    var activeQueue by remember { mutableStateOf<List<Track>>(emptyList()) }
    var nowPlaying by remember { mutableStateOf<Track?>(null) }
    var query by remember { mutableStateOf("") }
    var showLiked by remember { mutableStateOf(false) }
    var libraryLoading by remember { mutableStateOf(false) }
    var libraryError by remember { mutableStateOf<String?>(null) }
    var bridgeUrl by remember { mutableStateOf("") }
    var bridgeToken by remember { mutableStateOf("") }
    var bridgeReady by remember { mutableStateOf(false) }
    var bridgeMessage by remember { mutableStateOf<String?>(null) }
    var remoteResults by remember { mutableStateOf<List<Track>>(emptyList()) }
    var remoteQuery by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var position by remember { mutableLongStateOf(0L) }
    var duration by remember { mutableLongStateOf(0L) }
    val scope = rememberCoroutineScope()
    val audioPermission = remember {
        if (Build.VERSION.SDK_INT >= 33) Manifest.permission.READ_MEDIA_AUDIO
        else Manifest.permission.READ_EXTERNAL_STORAGE
    }
    var hasAudioPermission by remember {
        mutableStateOf(ContextCompat.checkSelfPermission(context, audioPermission) == PackageManager.PERMISSION_GRANTED)
    }
    val permissionRequest = androidx.activity.compose.rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        hasAudioPermission = granted
        if (!granted) libraryError = "Allow music access to play files stored on this phone. You can still connect to another Melodex."
    }

    LaunchedEffect(hasAudioPermission) {
        if (hasAudioPermission) {
            libraryLoading = true
            libraryError = null
            try {
                tracks = withContext(Dispatchers.IO) { LocalLibrary.read(context) }
            } catch (_: Exception) {
                libraryError = "Melodex could not read the music library. Check Android's music permission and try again."
            } finally {
                libraryLoading = false
            }
        }
    }

    LaunchedEffect(player, activeQueue) {
        while (player != null) {
            val itemIndex = player.currentMediaItemIndex
            if (itemIndex in activeQueue.indices) {
                nowPlaying = activeQueue[itemIndex]
            } else if (activeQueue.isEmpty()) {
                val item = player.currentMediaItem
                val metadata = item?.mediaMetadata
                if (item != null && metadata?.title != null) {
                    nowPlaying = Track(
                        id = item.mediaId,
                        title = metadata.title.toString(),
                        artist = metadata.artist?.toString().orEmpty(),
                        album = metadata.albumTitle?.toString().orEmpty(),
                        uri = item.localConfiguration?.uri ?: android.net.Uri.EMPTY,
                        artworkUri = metadata.artworkUri,
                        durationMs = player.duration.takeIf { it > 0L } ?: 0L,
                        source = if (item.mediaId.startsWith("bridge:")) Track.Source.BRIDGE else Track.Source.LOCAL,
                    )
                }
            }
            position = player.currentPosition.coerceAtLeast(0L)
            duration = player.duration.takeIf { it > 0L } ?: nowPlaying?.durationMs ?: 0L
            delay(500)
        }
    }

    fun playQueue(queue: List<Track>, startIndex: Int = 0) {
        val controller = player ?: return
        if (queue.isEmpty()) return
        activeQueue = queue
        val mediaItems = queue.map { track ->
            MediaItem.Builder()
                .setMediaId(track.id)
                .setUri(track.uri)
                .setMediaMetadata(
                    MediaMetadata.Builder()
                        .setTitle(track.title)
                        .setArtist(track.artist)
                        .setAlbumTitle(track.album)
                        .setArtworkUri(track.artworkUri)
                        .build(),
                )
                .build()
        }
        controller.setMediaItems(mediaItems, startIndex.coerceIn(queue.indices), 0L)
        controller.prepare()
        controller.play()
        nowPlaying = queue[startIndex.coerceIn(queue.indices)]
    }

    val colors = darkColorScheme(
        primary = Color(0xFFD5F56B),
        onPrimary = Color(0xFF19200B),
        secondary = Color(0xFF9AC6B4),
        background = Color(0xFF0D1110),
        surface = Color(0xFF151B19),
        surfaceVariant = Color(0xFF222A27),
        onSurface = Color(0xFFF1F4EF),
        onSurfaceVariant = Color(0xFFB5C0B8),
    )

    MaterialTheme(colorScheme = colors) {
        Scaffold(
            containerColor = colors.background,
            topBar = {
                TopAppBar(
                    title = {
                        Column {
                            Text("Melodex", fontWeight = FontWeight.SemiBold)
                            Text(
                                if (selectedTab == AppTab.MUSIC) "Your music, ready to play" else "Connect another Melodex",
                                style = MaterialTheme.typography.labelSmall,
                                color = colors.onSurfaceVariant,
                            )
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = colors.background),
                )
            },
            bottomBar = {
                NavigationBar(containerColor = colors.surface) {
                    NavigationBarItem(
                        selected = selectedTab == AppTab.MUSIC,
                        onClick = { selectedTab = AppTab.MUSIC },
                        icon = { Text("♫", fontSize = 21.sp) },
                        label = { Text("My Music") },
                    )
                    NavigationBarItem(
                        selected = selectedTab == AppTab.CONNECT,
                        onClick = { selectedTab = AppTab.CONNECT },
                        icon = { Text("⌁", fontSize = 21.sp) },
                        label = { Text("Connect") },
                    )
                }
            },
        ) { padding ->
            Column(Modifier.fillMaxSize().padding(padding)) {
                if (selectedTab == AppTab.MUSIC) {
                    if (!hasAudioPermission) {
                        FirstRun(
                            playerReady = player != null,
                            onStart = { permissionRequest.launch(audioPermission) },
                            onConnect = { selectedTab = AppTab.CONNECT },
                        )
                    } else {
                        MusicLibrary(
                            tracks = tracks,
                            likedIds = likedIds,
                            showLiked = showLiked,
                            query = query,
                            loading = libraryLoading,
                            error = libraryError,
                            playerReady = player != null,
                            nowPlaying = nowPlaying,
                            position = position,
                            duration = duration,
                            isPlaying = player?.isPlaying == true,
                            onQuery = { query = it },
                            onShowLiked = { showLiked = it },
                            onRefresh = {
                                scope.launch {
                                    libraryLoading = true
                                    try { tracks = withContext(Dispatchers.IO) { LocalLibrary.read(context) } }
                                    catch (_: Exception) { libraryError = "Could not refresh the library. Try again." }
                                    finally { libraryLoading = false }
                                }
                            },
                            onPlay = { selected -> playQueue(tracks, tracks.indexOfFirst { it.id == selected.id }.coerceAtLeast(0)) },
                            onPlaySomething = {
                                if (tracks.isNotEmpty()) playQueue(tracks, tracks.indices.random())
                            },
                            onToggleLike = { track ->
                                if (track.id in likedIds) likedIds.remove(track.id) else likedIds.add(track.id)
                                prefs.edit().putStringSet("liked_tracks", likedIds.toSet()).apply()
                            },
                            onTogglePlayback = { if (player?.isPlaying == true) player.pause() else player?.play() },
                            onPrevious = { player?.seekToPreviousMediaItem() },
                            onNext = { player?.seekToNextMediaItem() },
                            onSeek = { player?.seekTo(it.toLong()) },
                        )
                    }
                } else {
                    ConnectScreen(
                        bridgeUrl = bridgeUrl,
                        token = bridgeToken,
                        connected = bridgeReady,
                        message = bridgeMessage,
                        query = remoteQuery,
                        results = remoteResults,
                        busy = busy,
                        nowPlayingId = nowPlaying?.id,
                        onUrl = { bridgeUrl = it; bridgeReady = false },
                        onToken = { bridgeToken = it; bridgeReady = false },
                        onQuery = { remoteQuery = it },
                        onConnect = {
                            scope.launch {
                                busy = true
                                bridgeMessage = null
                                try {
                                    val count = withContext(Dispatchers.IO) { BridgeClient(bridgeUrl, bridgeToken).connect() }
                                    bridgeReady = true
                                    bridgeMessage = if (count == 1) "Connected · 1 source ready" else "Connected · $count sources ready"
                                } catch (e: Exception) {
                                    bridgeReady = false
                                    bridgeMessage = e.message ?: "Could not reach Melodex. Check the address and try again."
                                } finally { busy = false }
                            }
                        },
                        onSearch = {
                            scope.launch {
                                busy = true
                                bridgeMessage = null
                                try {
                                    remoteResults = withContext(Dispatchers.IO) { BridgeClient(bridgeUrl, bridgeToken).search(remoteQuery) }
                                    if (remoteResults.isEmpty()) bridgeMessage = "No matches yet. Try another search."
                                } catch (e: Exception) {
                                    bridgeReady = false
                                    bridgeMessage = e.message ?: "Search failed. Check the connection and try again."
                                } finally { busy = false }
                            }
                        },
                        onPlay = { track ->
                            scope.launch {
                                busy = true
                                bridgeMessage = null
                                try {
                                    val resolved = withContext(Dispatchers.IO) { BridgeClient(bridgeUrl, bridgeToken).resolve(track) }
                                    playQueue(listOf(resolved))
                                } catch (e: Exception) {
                                    bridgeMessage = e.message ?: "This track could not be played."
                                } finally { busy = false }
                            }
                        },
                    )
                }
            }
        }
    }
}

@Composable
private fun FirstRun(playerReady: Boolean, onStart: () -> Unit, onConnect: () -> Unit) {
    Column(
        Modifier.fillMaxSize().padding(horizontal = 24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.Start,
    ) {
        Text("♫", fontSize = 48.sp, color = MaterialTheme.colorScheme.primary)
        Spacer(Modifier.height(22.dp))
        Text("Your music,\nall in one Flow.", style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(12.dp))
        Text(
            "Play music stored on this phone, or connect to a Melodex library on your home network.",
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(28.dp))
        Button(onClick = onStart, modifier = Modifier.fillMaxWidth().height(54.dp), enabled = playerReady) {
            Text(if (playerReady) "Play something" else "Starting your player…")
        }
        Spacer(Modifier.height(10.dp))
        OutlinedButton(onClick = onConnect, modifier = Modifier.fillMaxWidth().height(52.dp)) {
            Text("Connect to another Melodex")
        }
        Spacer(Modifier.height(14.dp))
        Text("Your files stay on your phone. Melodex does not upload your music.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun MusicLibrary(
    tracks: List<Track>,
    likedIds: List<String>,
    showLiked: Boolean,
    query: String,
    loading: Boolean,
    error: String?,
    playerReady: Boolean,
    nowPlaying: Track?,
    position: Long,
    duration: Long,
    isPlaying: Boolean,
    onQuery: (String) -> Unit,
    onShowLiked: (Boolean) -> Unit,
    onRefresh: () -> Unit,
    onPlay: (Track) -> Unit,
    onPlaySomething: () -> Unit,
    onToggleLike: (Track) -> Unit,
    onTogglePlayback: () -> Unit,
    onPrevious: () -> Unit,
    onNext: () -> Unit,
    onSeek: (Float) -> Unit,
) {
    val visibleTracks = remember(tracks, likedIds, showLiked, query) {
        tracks.filter { track ->
            (!showLiked || track.id in likedIds) &&
                (query.isBlank() || "${track.title} ${track.artist} ${track.album}".contains(query, ignoreCase = true))
        }
    }
    Column(Modifier.fillMaxSize()) {
        if (nowPlaying != null) {
            NowPlayingCard(
                track = nowPlaying,
                liked = nowPlaying.id in likedIds,
                position = position,
                duration = duration,
                playing = isPlaying,
                onLike = { onToggleLike(nowPlaying) },
                onTogglePlayback = onTogglePlayback,
                onPrevious = onPrevious,
                onNext = onNext,
                onSeek = onSeek,
            )
        }
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 18.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text("My Music", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
            TextButton(onClick = onRefresh, enabled = !loading) { Text("Refresh") }
        }
        if (tracks.isNotEmpty()) {
            Button(onClick = onPlaySomething, enabled = playerReady, modifier = Modifier.fillMaxWidth().padding(horizontal = 18.dp)) {
                Text("Play something")
            }
        }
        OutlinedTextField(
            value = query,
            onValueChange = onQuery,
            modifier = Modifier.fillMaxWidth().padding(horizontal = 18.dp, vertical = 10.dp),
            singleLine = true,
            placeholder = { Text("Find a song, artist, or album") },
        )
        Row(Modifier.padding(start = 18.dp, end = 18.dp, bottom = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(selected = !showLiked, onClick = { onShowLiked(false) }, label = { Text("All songs · ${tracks.size}") })
            FilterChip(selected = showLiked, onClick = { onShowLiked(true) }, label = { Text("Liked · ${likedIds.size}") })
        }
        when {
            loading -> Box(Modifier.fillMaxWidth().weight(1f), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            error != null -> EmptyState(error, "Try again")
            tracks.isEmpty() -> EmptyState("No music found on this phone yet.", "Add music, then refresh")
            visibleTracks.isEmpty() -> EmptyState(if (showLiked) "Liked songs will appear here." else "No matches. Try a different search.", null)
            else -> LazyColumn(Modifier.weight(1f), contentPadding = PaddingValues(bottom = 16.dp)) {
                items(visibleTracks, key = { it.id }) { track ->
                    TrackRow(track, liked = track.id in likedIds, onClick = { onPlay(track) }, onLike = { onToggleLike(track) })
                }
            }
        }
    }
}

@Composable
private fun NowPlayingCard(
    track: Track,
    liked: Boolean,
    position: Long,
    duration: Long,
    playing: Boolean,
    onLike: () -> Unit,
    onTogglePlayback: () -> Unit,
    onPrevious: () -> Unit,
    onNext: () -> Unit,
    onSeek: (Float) -> Unit,
) {
    Column(
        Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp)
            .clip(RoundedCornerShape(24.dp)).background(MaterialTheme.colorScheme.surface).padding(16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
            Artwork(track, Modifier.size(84.dp))
            Column(Modifier.weight(1f)) {
                Text("NOW PLAYING", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(5.dp))
                Text(track.title, maxLines = 2, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Text(track.artist, maxLines = 1, overflow = TextOverflow.Ellipsis, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            TextButton(onClick = onLike) { Text(if (liked) "♥" else "♡", fontSize = 25.sp) }
        }
        Slider(
            value = position.coerceAtMost(duration.coerceAtLeast(1L)).toFloat(),
            onValueChange = onSeek,
            valueRange = 0f..duration.coerceAtLeast(1L).toFloat(),
            enabled = duration > 0L,
            modifier = Modifier.height(32.dp),
        )
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(formatTime(position), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.weight(1f))
            Text(formatTime(duration), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = onPrevious) { Text("|◀", fontSize = 20.sp) }
            Button(onClick = onTogglePlayback, modifier = Modifier.padding(horizontal = 10.dp).size(58.dp), shape = RoundedCornerShape(50)) {
                Text(if (playing) "Ⅱ" else "▶", fontSize = 21.sp)
            }
            TextButton(onClick = onNext) { Text("▶|", fontSize = 20.sp) }
        }
    }
}

@Composable
private fun ConnectScreen(
    bridgeUrl: String,
    token: String,
    connected: Boolean,
    message: String?,
    query: String,
    results: List<Track>,
    busy: Boolean,
    nowPlayingId: String?,
    onUrl: (String) -> Unit,
    onToken: (String) -> Unit,
    onQuery: (String) -> Unit,
    onConnect: () -> Unit,
    onSearch: () -> Unit,
    onPlay: (Track) -> Unit,
) {
    Column(Modifier.fillMaxSize().padding(horizontal = 18.dp)) {
        Text("Keep your music at home", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 18.dp))
        Text(
            "Connect to Melodex on your computer or NAS over the same home network. Your phone can also play its own music without a connection.",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(top = 6.dp, bottom = 14.dp),
        )
        OutlinedTextField(
            value = bridgeUrl,
            onValueChange = onUrl,
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Melodex address") },
            placeholder = { Text("http://192.168.1.42:8766") },
            singleLine = true,
        )
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(
            value = token,
            onValueChange = onToken,
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Bridge token") },
            visualTransformation = PasswordVisualTransformation(),
            singleLine = true,
        )
        Button(onClick = onConnect, enabled = !busy && bridgeUrl.isNotBlank() && token.isNotBlank(), modifier = Modifier.fillMaxWidth().padding(top = 12.dp).height(50.dp)) {
            if (busy) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp) else Text(if (connected) "Reconnect" else "Connect")
        }
        if (connected) {
            Text("Connected", color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelLarge, modifier = Modifier.padding(top = 10.dp))
            Row(Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(value = query, onValueChange = onQuery, modifier = Modifier.weight(1f), singleLine = true, placeholder = { Text("Search connected music") })
                Button(onClick = onSearch, enabled = !busy && query.isNotBlank()) { Text("Search") }
            }
        }
        if (!message.isNullOrBlank()) {
            Text(message, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(vertical = 8.dp))
        }
        LazyColumn(Modifier.weight(1f), contentPadding = PaddingValues(bottom = 12.dp)) {
            items(results, key = { it.id }) { track ->
                TrackRow(
                    track = track,
                    liked = false,
                    onClick = { onPlay(track) },
                    onLike = { onPlay(track) },
                    trailing = if (track.id == nowPlayingId) "Playing" else "Play",
                )
            }
        }
    }
}

@Composable
private fun TrackRow(
    track: Track,
    liked: Boolean,
    onClick: () -> Unit,
    onLike: () -> Unit,
    trailing: String? = null,
) {
    ListItem(
        headlineContent = { Text(track.title, maxLines = 1, overflow = TextOverflow.Ellipsis) },
        supportingContent = {
            Text(
                listOf(track.artist, track.album).filter(String::isNotBlank).joinToString(" · "),
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        },
        leadingContent = { Artwork(track, Modifier.size(52.dp)) },
        trailingContent = {
            if (trailing != null) Text(trailing, color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelMedium)
            else TextButton(onClick = onLike) { Text(if (liked) "♥" else "♡", fontSize = 21.sp) }
        },
        modifier = Modifier.clickable(onClick = onClick),
        colors = ListItemDefaults.colors(containerColor = Color.Transparent),
    )
}

@Composable
private fun Artwork(track: Track, modifier: Modifier = Modifier) {
    Box(
        modifier.clip(RoundedCornerShape(14.dp)).background(MaterialTheme.colorScheme.surfaceVariant),
        contentAlignment = Alignment.Center,
    ) {
        if (track.artworkUri != null) {
            AsyncImage(
                model = track.artworkUri,
                contentDescription = "${track.album.ifBlank { track.title }} artwork",
                modifier = Modifier.fillMaxSize(),
                contentScale = androidx.compose.ui.layout.ContentScale.Crop,
            )
        } else {
            Text("♫", color = MaterialTheme.colorScheme.primary, fontSize = 21.sp)
        }
    }
}

@Composable
private fun EmptyState(message: String, actionLabel: String?) {
    Column(
        Modifier.fillMaxWidth().weight(1f).padding(28.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("♫", color = MaterialTheme.colorScheme.primary, fontSize = 36.sp)
        Spacer(Modifier.height(10.dp))
        Text(message, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyLarge)
        if (actionLabel != null) Text(actionLabel, color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelLarge, modifier = Modifier.padding(top = 8.dp))
    }
}

private fun formatTime(milliseconds: Long): String {
    val seconds = (milliseconds.coerceAtLeast(0L) / 1000L)
    return "%d:%02d".format(seconds / 60, seconds % 60)
}

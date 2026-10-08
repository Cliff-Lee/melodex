package com.melodex.app

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import org.json.JSONObject
import java.net.URI
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

data class StoredBridgeConnection(
    val baseUrl: String,
    val token: String,
    val displayName: String,
    val deviceId: String = ""
)

data class BridgePairingPayload(
    val baseUrl: String,
    val code: String,
    val displayName: String
)

object BridgePairingPayloadParser {
    private fun isLocalHost(host: String): Boolean {
        if (host.endsWith(".local")) return true
        val parts = host.split(".")
        if (parts.size != 4) return false
        val octets = parts.map { it.toIntOrNull() ?: -1 }
        if (octets.any { it !in 0..255 }) return false
        return octets[0] == 10 ||
            (octets[0] == 192 && octets[1] == 168) ||
            (octets[0] == 172 && octets[1] in 16..31) ||
            (octets[0] == 169 && octets[1] == 254)
    }

    fun parse(raw: String): BridgePairingPayload {
        val json = JSONObject(raw)
        require(json.optString("type") == "melodex-bridge-pairing") {
            "That QR code is not a Melodex Bridge pairing code."
        }
        require(json.optInt("version") == 1) { "This Melodex pairing code version is not supported." }

        val baseUrl = json.optString("url").trim().trimEnd('/')
        val uri = try {
            URI(baseUrl)
        } catch (_: Exception) {
            throw IllegalArgumentException("The pairing code contains an invalid Bridge address.")
        }
        val host = uri.host?.lowercase().orEmpty()
        require(
            uri.scheme in setOf("http", "https") &&
                host.isNotBlank() &&
                host != "localhost" &&
                host != "0.0.0.0" &&
                host != "::" &&
                host != "::1" &&
                !host.startsWith("127.") &&
                isLocalHost(host) &&
                uri.userInfo == null &&
                uri.query == null &&
                uri.fragment == null &&
                (uri.path.isNullOrEmpty() || uri.path == "/")
        ) {
            "The pairing code does not contain a usable Bridge address."
        }

        val code = json.optString("code")
        require(code.length in 20..128) { "The pairing code is incomplete." }
        return BridgePairingPayload(
            baseUrl = baseUrl,
            code = code,
            displayName = json.optString("name").trim().ifBlank { "Melodex computer" }
        )
    }
}

object BridgeConnectionStore {
    private const val PREFS_NAME = "bridge_connection_encrypted"
    private const val KEY_ALIAS = "com.melodex.app.bridge-connection"
    private const val IV_KEY = "iv"
    private const val DATA_KEY = "data"

    @Synchronized
    fun save(context: Context, connection: StoredBridgeConnection) {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, encryptionKey())
        val plaintext = JSONObject()
            .put("base_url", connection.baseUrl)
            .put("token", connection.token)
            .put("display_name", connection.displayName)
            .put("device_id", connection.deviceId)
            .toString()
            .toByteArray(Charsets.UTF_8)
        val ciphertext = cipher.doFinal(plaintext)
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val committed = prefs.edit()
            .putString(IV_KEY, Base64.encodeToString(cipher.iv, Base64.NO_WRAP))
            .putString(DATA_KEY, Base64.encodeToString(ciphertext, Base64.NO_WRAP))
            .commit()
        check(committed) { "Could not save the encrypted Bridge connection." }
    }

    @Synchronized
    fun load(context: Context): StoredBridgeConnection? {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val ivValue = prefs.getString(IV_KEY, null) ?: return null
        val dataValue = prefs.getString(DATA_KEY, null) ?: return null
        return try {
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(
                Cipher.DECRYPT_MODE,
                encryptionKey(),
                GCMParameterSpec(128, Base64.decode(ivValue, Base64.NO_WRAP))
            )
            val plaintext = cipher.doFinal(Base64.decode(dataValue, Base64.NO_WRAP))
            val json = JSONObject(String(plaintext, Charsets.UTF_8))
            val baseUrl = json.optString("base_url")
            val token = json.optString("token")
            if (baseUrl.isBlank() || token.isBlank()) {
                clear(context)
                null
            } else {
                StoredBridgeConnection(
                    baseUrl = baseUrl,
                    token = token,
                    displayName = json.optString("display_name").ifBlank { "Melodex computer" },
                    deviceId = json.optString("device_id")
                )
            }
        } catch (_: Exception) {
            clear(context)
            null
        }
    }

    @Synchronized
    fun clear(context: Context) {
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE).edit().clear().commit()
        try {
            val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
            if (keyStore.containsAlias(KEY_ALIAS)) keyStore.deleteEntry(KEY_ALIAS)
        } catch (_: Exception) {
            // Clearing app-private data remains useful if the key store is unavailable.
        }
    }

    private fun encryptionKey(): SecretKey {
        val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (keyStore.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        generator.init(
            KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
            )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true)
                .build()
        )
        return generator.generateKey()
    }
}

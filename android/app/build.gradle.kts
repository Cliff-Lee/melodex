plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

val playUploadStoreFile = providers.environmentVariable("MELODEX_UPLOAD_STORE_FILE").orNull
val playUploadStorePassword = providers.environmentVariable("MELODEX_UPLOAD_STORE_PASSWORD").orNull
val playUploadKeyAlias = providers.environmentVariable("MELODEX_UPLOAD_KEY_ALIAS").orNull
val playUploadKeyPassword = providers.environmentVariable("MELODEX_UPLOAD_KEY_PASSWORD").orNull
val playUploadSigningValues = listOf(
    playUploadStoreFile,
    playUploadStorePassword,
    playUploadKeyAlias,
    playUploadKeyPassword
)
val hasPlayUploadSigning = playUploadSigningValues.all { !it.isNullOrBlank() }
val hasAnyPlayUploadSigning = playUploadSigningValues.any { !it.isNullOrBlank() }
if (hasAnyPlayUploadSigning && !hasPlayUploadSigning) {
    throw GradleException("Set all four MELODEX_UPLOAD_* signing variables or leave all unset.")
}

android {
    namespace = "com.melodex.app"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.melodex.app"
        minSdk = 26
        targetSdk = 36
        versionCode = 724
        versionName = "0.7.24.dev0"
    }

    signingConfigs {
        if (hasPlayUploadSigning) {
            create("playUpload") {
                storeFile = file(playUploadStoreFile!!)
                storePassword = playUploadStorePassword
                keyAlias = playUploadKeyAlias
                keyPassword = playUploadKeyPassword
            }
        }
    }

    buildTypes {
        getByName("release") {
            if (hasPlayUploadSigning) {
                signingConfig = signingConfigs.getByName("playUpload")
            }
        }
    }

    buildFeatures { compose = true }
    composeOptions { kotlinCompilerExtensionVersion = "1.5.14" }
    packaging { resources.excludes += "/META-INF/{AL2.0,LGPL2.1}" }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-compose:1.10.0")
    implementation(platform("androidx.compose:compose-bom:2025.01.00"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.media3:media3-exoplayer:1.5.1")
    implementation("androidx.media3:media3-session:1.5.1")
    implementation("androidx.media3:media3-common:1.5.1")
    implementation("com.journeyapps:zxing-android-embedded:4.3.0")
    debugImplementation("androidx.compose.ui:ui-tooling")
}

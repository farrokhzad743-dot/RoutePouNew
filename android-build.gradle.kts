// RoutePou Android app. ./stage-android.sh copies the flat repository files into the standard
// Android project layout and uses this file as that project's build script.
plugins {
    id("com.android.application") version "8.7.3"
    id("org.jetbrains.kotlin.android") version "2.0.21"
}

android {
    namespace = "com.pou.routepou"
    compileSdk = 35
    buildToolsVersion = "35.0.0"

    defaultConfig {
        applicationId = "com.pou.routepou"
        minSdk = 26
        targetSdk = 35
        versionCode = 27
        versionName = "0.27.0-beta"

        // Must match the ABIs gomobile packs into relaywg.aar.
        ndk {
            abiFilters += listOf("arm64-v8a", "armeabi-v7a", "x86_64", "x86")
        }
    }

    buildFeatures {
        buildConfig = true
    }

    // Release signing comes from environment variables (GitHub secrets in CI).
    // Without them the release APK is signed with the debug key: installable, but a later
    // properly signed release cannot update it in place.
    val keystoreFile = System.getenv("ROUTEPOU_KEYSTORE_FILE")
    if (!keystoreFile.isNullOrBlank() && file(keystoreFile).exists()) {
        signingConfigs {
            create("release") {
                storeFile = file(keystoreFile)
                storePassword = System.getenv("ROUTEPOU_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("ROUTEPOU_KEY_ALIAS")
                keyPassword = System.getenv("ROUTEPOU_KEY_PASSWORD")
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildTypes {
        getByName("debug") {
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
        }
        getByName("release") {
            signingConfig = signingConfigs.findByName("release") ?: signingConfigs.getByName("debug")
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    lint {
        // Lint is advisory here: a style warning must never block a release APK.
        abortOnError = false
        checkReleaseBuilds = false
    }

    packaging {
        jniLibs {
            useLegacyPackaging = false
        }
        resources {
            // Library metadata that can collide when several jars carry the same file name.
            excludes += setOf(
                "META-INF/versions/9/OSGI-INF/MANIFEST.MF",
                "META-INF/{AL2.0,LGPL2.1}",
                "META-INF/DEPENDENCIES",
            )
        }
    }
}

dependencies {
    // relaywg.aar (Go WireGuard engine) is optional: without it the app builds and runs in proxy
    // mode, and Full Tunnel reports itself unavailable.
    implementation(fileTree(mapOf("dir" to "libs", "include" to listOf("*.aar"))))
    implementation("com.google.zxing:core:3.5.3")
    implementation("org.bouncycastle:bcprov-jdk18on:1.78.1")
}

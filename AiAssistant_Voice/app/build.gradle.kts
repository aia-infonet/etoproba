plugins {
    id ("com.android.application")
    id ("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.ai.aiassistant_voice"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.ai.aiassistant_voice"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables {
            useSupportLibrary = true
        }

        buildTypes {
            release {
                isMinifyEnabled = false
                proguardFiles (
                    getDefaultProguardFile("proguard-android-optimize.txt"),
                    "proguard-rules.pro"
                )
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

    buildFeatures {
        viewBinding = true
        compose = true
    }

    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.8"
    }
    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }

buildToolsVersion = "34.0.0"


    dependencies {

        implementation ("androidx.core:core-ktx:1.12.0")
        implementation ("androidx.appcompat:appcompat:1.6.1")
        implementation ("com.google.android.material:material:1.11.0")
        implementation ("androidx.constraintlayout:constraintlayout:2.1.4")
        implementation ("androidx.fragment:fragment-ktx:1.6.2")

        //для compose
        implementation("androidx.activity:activity-compose:1.9.0") // для Activity
        implementation("androidx.compose.ui:ui")
        implementation("androidx.compose.material3:material3:1.3.0") // или material
        implementation("androidx.compose.ui:ui-tooling-preview")
        implementation("androidx.compose.foundation:foundation:1.6.8")

        // Navigation
        implementation ("androidx.navigation:navigation-fragment-ktx:2.7.5")
        implementation ("androidx.navigation:navigation-ui-ktx:2.7.5")

        // WebSocket клиент
        implementation ("com.squareup.okhttp3:okhttp:4.12.0")
        implementation ("com.squareup.okhttp3:logging-interceptor:4.12.0")

        // Gson для JSON парсинг
        implementation ("com.google.code.gson:gson:2.10.1")

        // Vosk STT (распознавание речи)
        implementation ("com.alphacephei:vosk-android:0.3.47")

        // Lifecycle
        implementation ("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
        implementation ("androidx.lifecycle:lifecycle-viewmodel-ktx:2.7.0")
        implementation ("androidx.lifecycle:lifecycle-livedata-ktx:2.7.0")

        // Audio
        implementation ("androidx.media:media:1.7.0")

        // Coroutines для асинхронности
        implementation ("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")

        testImplementation ("junit:junit:4.13.2")
    }
}

configurations.all {
    resolutionStrategy {
        force ("org.jetbrains.kotlin:kotlin-stdlib:1.9.22")
    }
}
dependencies {
    implementation(libs.androidx.monitor)
    implementation(libs.androidx.junit.ktx)
    androidTestImplementation("junit:junit:4.12")
}

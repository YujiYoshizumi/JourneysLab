plugins {
    // AGP 9 は Kotlin サポートを内蔵しているため org.jetbrains.kotlin.android は適用しない。
    alias(libs.plugins.android.application)
}

/**
 * ビルド時のバグ注入。
 *
 * `-Pjourneylab.bugs=B01` で B01 を注入し、未指定（空）なら clean ビルドになる。
 * 注入の有無は、被験エージェントが端末上で観測できるもの（アプリ名・バージョン名・
 * 画面・contentDescription・Logcat）には一切出さない。
 */
val injectedBugs: String = (project.findProperty("journeylab.bugs") as String? ?: "").trim()

android {
    namespace = "com.example.journeylab"
    compileSdk = 37

    defaultConfig {
        applicationId = "com.example.journeylab"
        minSdk = 29
        targetSdk = 37
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        buildConfigField("String", "FEATURE_FLAGS", "\"$injectedBugs\"")
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        viewBinding = true
        buildConfig = true
        compose = false
        aidl = false
        shaders = false
    }

    testOptions {
        // アニメーション有効時は Espresso が不安定になるため、試験実行中は無効化する。
        animationsDisabled = true
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

configurations.configureEach {
    // Compose は使わない。androidx.activity が推移的に引く Compose の注釈ライブラリも外す。
    exclude(group = "androidx.compose.runtime", module = "runtime-annotation")
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.appcompat)
    implementation(libs.androidx.activity.ktx)
    implementation(libs.androidx.fragment.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.recyclerview)
    implementation(libs.material)

    testImplementation(libs.junit)

    androidTestImplementation(libs.junit)
    androidTestImplementation(libs.androidx.test.core)
    androidTestImplementation(libs.androidx.test.runner)
    androidTestImplementation(libs.androidx.test.rules)
    androidTestImplementation(libs.androidx.test.ext.junit)
    androidTestImplementation(libs.androidx.test.espresso.core)
    androidTestImplementation(libs.androidx.test.espresso.contrib)
}

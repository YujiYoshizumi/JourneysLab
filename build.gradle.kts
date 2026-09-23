// Top-level build file. AGP 9 は Kotlin サポートを内蔵しているため、
// org.jetbrains.kotlin.android は適用しない。
plugins {
    alias(libs.plugins.android.application) apply false
}

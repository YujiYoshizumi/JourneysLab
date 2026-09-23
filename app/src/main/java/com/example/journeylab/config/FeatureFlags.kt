package com.example.journeylab.config

import com.example.journeylab.BuildConfig

/**
 * ビルド時に注入された「仕様からの逸脱」のフラグ。
 *
 * 値の出どころは `-Pjourneylab.bugs=...`。被験エージェントの判定が汚染されないよう、
 * この値は画面・contentDescription・Logcat・アプリ名・バージョン名のいずれにも出さない
 * （アプリはログ出力を一切行わない）。
 */
object FeatureFlags {

    private val flags: Set<String> = BuildConfig.FEATURE_FLAGS
        .split(',')
        .map { it.trim().uppercase() }
        .filter { it.isNotEmpty() }
        .toSet()

    fun isOn(id: String): Boolean = id.uppercase() in flags
}

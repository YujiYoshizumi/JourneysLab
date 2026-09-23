package com.example.journeylab

import android.os.Bundle
import android.view.Menu
import android.view.MenuItem
import androidx.appcompat.app.AppCompatActivity
import androidx.fragment.app.Fragment
import androidx.fragment.app.FragmentManager
import com.example.journeylab.config.FeatureFlags
import com.example.journeylab.databinding.ActivityMainBinding
import com.example.journeylab.ui.cart.CartFragment
import com.example.journeylab.ui.home.HomeFragment
import com.google.android.material.dialog.MaterialAlertDialogBuilder

/**
 * 単一 Activity。画面ごとの Fragment を [FragmentManager] で切り替える。
 *
 * トップバーのカートアイコンとオーバーフローメニューは、
 * ホーム画面と商品詳細画面にだけ表示する。
 */
class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding

    /** 現在の画面でショップ用のメニュー（カートアイコン／オーバーフロー）を出すか。 */
    private var showShopMenu = true

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)
        setSupportActionBar(binding.toolbar)

        binding.toolbar.setNavigationContentDescription(R.string.navigate_up)
        binding.toolbar.setNavigationOnClickListener { onBackPressedDispatcher.onBackPressed() }
        supportFragmentManager.addOnBackStackChangedListener { updateUpButton() }

        if (savedInstanceState == null) {
            supportFragmentManager.beginTransaction()
                .replace(R.id.fragmentContainer, HomeFragment(), HomeFragment.TAG)
                .commit()
        }
        updateUpButton()
    }

    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menuInflater.inflate(R.menu.menu_main, menu)
        return true
    }

    override fun onPrepareOptionsMenu(menu: Menu): Boolean {
        for (index in 0 until menu.size()) {
            menu.getItem(index).isVisible = showShopMenu
        }
        return super.onPrepareOptionsMenu(menu)
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean = when (item.itemId) {
        R.id.action_cart -> {
            // B01: トップバーのカートアイコンをタップしても何も起きない
            //（オーバーフローメニューの「カート」からは従来どおり遷移できる）
            if (!FeatureFlags.isOn("B01")) {
                openScreen(CartFragment(), CartFragment.TAG)
            }
            true
        }

        R.id.action_overflow_cart -> {
            openScreen(CartFragment(), CartFragment.TAG)
            true
        }

        R.id.action_overflow_about -> {
            showAboutDialog()
            true
        }

        else -> super.onOptionsItemSelected(item)
    }

    /** 各画面から呼ばれ、トップバーの表示内容をそろえる。 */
    fun configureToolbar(title: CharSequence, showShopMenu: Boolean) {
        supportActionBar?.title = title
        if (this.showShopMenu != showShopMenu) {
            this.showShopMenu = showShopMenu
            invalidateOptionsMenu()
        }
    }

    /** 同じ画面を重ねて開かないようにしつつ、指定の Fragment へ遷移する。 */
    fun openScreen(fragment: Fragment, tag: String) {
        val current = supportFragmentManager.findFragmentById(R.id.fragmentContainer)
        if (current != null && current.tag == tag) return
        supportFragmentManager.beginTransaction()
            .replace(R.id.fragmentContainer, fragment, tag)
            .addToBackStack(tag)
            .commit()
    }

    /** ホーム画面まで戻る。 */
    fun goHome() {
        supportFragmentManager.popBackStack(null, FragmentManager.POP_BACK_STACK_INCLUSIVE)
    }

    private fun showAboutDialog() {
        // バージョン名やビルド情報は表示しない（注入状況の漏洩を防ぐため）。
        MaterialAlertDialogBuilder(this)
            .setTitle(R.string.about_title)
            .setMessage(R.string.about_message)
            .setPositiveButton(R.string.about_close) { dialog, _ -> dialog.dismiss() }
            .show()
    }

    private fun updateUpButton() {
        supportActionBar?.setDisplayHomeAsUpEnabled(supportFragmentManager.backStackEntryCount > 0)
    }
}

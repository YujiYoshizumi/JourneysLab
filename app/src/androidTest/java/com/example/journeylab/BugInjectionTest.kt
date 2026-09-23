package com.example.journeylab

import androidx.test.espresso.Espresso.onView
import androidx.test.espresso.assertion.ViewAssertions.matches
import androidx.test.espresso.matcher.ViewMatchers.isDisplayed
import androidx.test.espresso.matcher.ViewMatchers.withId
import androidx.test.ext.junit.rules.ActivityScenarioRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.filters.LargeTest
import com.example.journeylab.TestSupport.doesNotExistOrIsHidden
import com.example.journeylab.TestSupport.openOverflowItem
import com.example.journeylab.TestSupport.openProductFromHome
import com.example.journeylab.TestSupport.tapCartIcon
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * B01 を注入したビルドで、カートアイコンが無反応になり、メニューからはカートへ遷移できることを検証する。
 *
 * `eval/verify_ground_truth.sh` が、B01 ビルドに対してだけ実行する。
 */
@RunWith(AndroidJUnit4::class)
@LargeTest
class BugInjectionTest {

    @get:Rule
    val rule = ActivityScenarioRule(MainActivity::class.java)

    /** ホーム画面のカートアイコンは無反応。 */
    @Test
    fun b01_cartIconDoesNothingOnHome() {
        tapCartIcon()
        onView(withId(R.id.homeHeading)).check(matches(isDisplayed()))
        onView(withId(R.id.cartTotalText)).check(doesNotExistOrIsHidden())
    }

    /** 商品詳細画面のカートアイコンも無反応。 */
    @Test
    fun b01_cartIconDoesNothingOnProductDetail() {
        openProductFromHome("トートバッグ")
        tapCartIcon()
        onView(withId(R.id.detailProductName)).check(matches(isDisplayed()))
        onView(withId(R.id.cartTotalText)).check(doesNotExistOrIsHidden())
    }

    /** メニューの「カート」からは従来どおり遷移できる。 */
    @Test
    fun b01_overflowMenuStillOpensTheCart() {
        openOverflowItem("カート")
        onView(withId(R.id.cartTotalText)).check(matches(isDisplayed()))
    }
}

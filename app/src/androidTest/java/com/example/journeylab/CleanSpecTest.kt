package com.example.journeylab

import androidx.test.espresso.Espresso.onView
import androidx.test.espresso.Espresso.pressBack
import androidx.test.espresso.action.ViewActions.click
import androidx.test.espresso.assertion.ViewAssertions.matches
import androidx.test.espresso.matcher.ViewMatchers.isDisplayed
import androidx.test.espresso.matcher.ViewMatchers.isEnabled
import androidx.test.espresso.matcher.ViewMatchers.withId
import androidx.test.espresso.matcher.ViewMatchers.withText
import androidx.test.ext.junit.rules.ActivityScenarioRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.filters.LargeTest
import com.example.journeylab.TestSupport.addProductToCartFromHome
import com.example.journeylab.TestSupport.hasItemCount
import com.example.journeylab.TestSupport.openOverflowItem
import com.example.journeylab.TestSupport.openProductFromHome
import com.example.journeylab.TestSupport.tapCartIcon
import org.hamcrest.Matchers.not
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * clean ビルド（バグ未注入）の表示・画面遷移・購入処理を検証する。
 *
 * `eval/verify_ground_truth.sh` が、このクラスを clean ビルドに対してだけ実行する。
 */
@RunWith(AndroidJUnit4::class)
@LargeTest
class CleanSpecTest {

    @get:Rule
    val rule = ActivityScenarioRule(MainActivity::class.java)

    @Test
    fun homeShowsHeadingAndAllFourProductsWithoutScrolling() {
        onView(withId(R.id.homeHeading)).check(matches(withText("本日のおすすめ")))
        onView(withId(R.id.productList)).check(hasItemCount(4))
        onView(withText("ブルーマグカップ")).check(matches(isDisplayed()))
        onView(withText("ノートブック A5")).check(matches(isDisplayed()))
        onView(withText("トートバッグ")).check(matches(isDisplayed()))
        onView(withText("デスクライト")).check(matches(isDisplayed()))
        onView(withText("¥1,280")).check(matches(isDisplayed()))
    }

    @Test
    fun cartIconOpensCartScreenFromHome() {
        tapCartIcon()
        onView(withId(R.id.cartTotalText)).check(matches(isDisplayed()))
    }

    @Test
    fun cartIconOpensCartScreenFromProductDetail() {
        openProductFromHome("トートバッグ")
        tapCartIcon()
        onView(withId(R.id.cartTotalText)).check(matches(isDisplayed()))
    }

    @Test
    fun overflowMenuAlsoOpensCartScreen() {
        openOverflowItem("カート")
        onView(withId(R.id.cartTotalText)).check(matches(isDisplayed()))
    }

    @Test
    fun aboutDialogShowsNoBuildInformation() {
        openOverflowItem("このアプリについて")
        onView(withText("JourneyLab サンプルアプリ")).check(matches(isDisplayed()))
        // バージョン名やビルド情報は出さない
        onView(withText("1.0")).check(TestSupport.doesNotExistOrIsHidden())
    }

    @Test
    fun addingAProductPutsItInTheCart() {
        openProductFromHome("トートバッグ")
        onView(withId(R.id.detailProductName)).check(matches(withText("トートバッグ")))
        onView(withId(R.id.detailProductPrice)).check(matches(withText("¥2,200")))
        onView(withId(R.id.addToCartButton)).perform(click())
        onView(withText("カートに追加しました")).check(matches(isDisplayed()))

        TestSupport.dismissSnackbarIfPresent()
        tapCartIcon()
        onView(withId(R.id.cartList)).check(hasItemCount(1))
        onView(withId(R.id.cartItemName)).check(matches(withText("トートバッグ")))
        onView(withId(R.id.cartItemQuantity)).check(matches(withText("数量 1")))
        onView(withId(R.id.cartItemSubtotal)).check(matches(withText("小計 ¥2,200")))
        onView(withId(R.id.cartTotalText)).check(matches(withText("合計 ¥2,200")))
    }

    @Test
    fun cartTotalIsTheSumOfEveryLine() {
        addProductToCartFromHome("ノートブック A5")
        addProductToCartFromHome("トートバッグ")
        tapCartIcon()
        onView(withId(R.id.cartList)).check(hasItemCount(2))
        onView(withId(R.id.cartTotalText)).check(matches(withText("合計 ¥3,080")))
    }

    @Test
    fun checkoutIsDisabledWhenTheCartIsEmpty() {
        tapCartIcon()
        onView(withId(R.id.cartEmptyText)).check(matches(isDisplayed()))
        onView(withId(R.id.checkoutButton)).check(matches(not(isEnabled())))
    }

    @Test
    fun checkoutShowsOrderCompleteAndEmptiesTheCart() {
        addProductToCartFromHome("トートバッグ")
        tapCartIcon()
        onView(withId(R.id.checkoutButton)).perform(click())

        onView(withId(R.id.orderCompleteMessage)).check(matches(withText("ご注文ありがとうございました")))
        onView(withId(R.id.orderNumberText)).check(matches(withText("注文番号 ORDER-0001")))
        onView(withId(R.id.backToHomeButton)).perform(click())

        onView(withId(R.id.homeHeading)).check(matches(isDisplayed()))
        tapCartIcon()
        onView(withId(R.id.cartEmptyText)).check(matches(isDisplayed()))
        onView(withId(R.id.cartList)).check(hasItemCount(0))
    }

    @Test
    fun orderNumbersAreSequentialWithinOneLaunch() {
        addProductToCartFromHome("ブルーマグカップ")
        tapCartIcon()
        onView(withId(R.id.checkoutButton)).perform(click())
        onView(withId(R.id.orderNumberText)).check(matches(withText("注文番号 ORDER-0001")))
        onView(withId(R.id.backToHomeButton)).perform(click())

        addProductToCartFromHome("デスクライト")
        tapCartIcon()
        onView(withId(R.id.checkoutButton)).perform(click())
        onView(withId(R.id.orderNumberText)).check(matches(withText("注文番号 ORDER-0002")))
    }

    @Test
    fun shopMenuIsHiddenOnCartAndOrderCompleteScreens() {
        addProductToCartFromHome("トートバッグ")
        tapCartIcon()
        // カート画面ではカートアイコンとオーバーフローを出さない
        onView(withId(R.id.action_cart)).check(TestSupport.doesNotExistOrIsHidden())
        onView(withId(R.id.checkoutButton)).perform(click())
        onView(withId(R.id.action_cart)).check(TestSupport.doesNotExistOrIsHidden())
        pressBack()
    }
}

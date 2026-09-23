package com.example.journeylab

import android.view.View
import androidx.recyclerview.widget.RecyclerView
import androidx.test.espresso.Espresso.onView
import androidx.test.espresso.Espresso.openActionBarOverflowOrOptionsMenu
import androidx.test.espresso.Espresso.pressBack
import androidx.test.espresso.NoMatchingViewException
import androidx.test.espresso.PerformException
import androidx.test.espresso.ViewAssertion
import androidx.test.espresso.action.ViewActions.click
import androidx.test.espresso.action.ViewActions.swipeRight
import androidx.test.espresso.contrib.RecyclerViewActions
import androidx.test.espresso.matcher.ViewMatchers.hasDescendant
import androidx.test.espresso.matcher.ViewMatchers.withId
import androidx.test.espresso.matcher.ViewMatchers.withText
import androidx.test.platform.app.InstrumentationRegistry
import org.hamcrest.Matchers.allOf
import org.junit.Assert.assertEquals

/** Journeys とは独立した Espresso テストで使う共通操作。 */
object TestSupport {

    fun openProductFromHome(name: String) {
        onView(withId(R.id.productList)).perform(
            RecyclerViewActions.scrollTo<RecyclerView.ViewHolder>(hasDescendant(withText(name))),
        )
        InstrumentationRegistry.getInstrumentation().waitForIdleSync()
        onView(allOf(withId(R.id.productCard), hasDescendant(withText(name)))).perform(click())
    }

    /** 商品詳細を開いて「カートに追加」を押し、ホームへ戻る。 */
    fun addProductToCartFromHome(name: String) {
        openProductFromHome(name)
        onView(withId(R.id.addToCartButton)).perform(click())
        pressBack()
        dismissSnackbarIfPresent()
    }

    fun dismissSnackbarIfPresent() {
        try {
            onView(withId(com.google.android.material.R.id.snackbar_text)).perform(swipeRight())
        } catch (_: NoMatchingViewException) {
            return
        } catch (_: PerformException) {
            return
        }
        InstrumentationRegistry.getInstrumentation().waitForIdleSync()
    }

    fun openOverflowItem(title: String) {
        openActionBarOverflowOrOptionsMenu(InstrumentationRegistry.getInstrumentation().targetContext)
        onView(withText(title)).perform(click())
    }

    fun tapCartIcon() {
        onView(withId(R.id.action_cart)).perform(click())
    }

    /** RecyclerView の要素数を検証する。 */
    fun hasItemCount(expected: Int): ViewAssertion =
        ViewAssertion { view: View?, noMatch: NoMatchingViewException? ->
            if (noMatch != null) throw noMatch
            val recyclerView = view as RecyclerView
            assertEquals(expected, recyclerView.adapter?.itemCount ?: -1)
        }

    /** 対象のビューが存在しない、または表示されていないことを許容する検証。 */
    fun doesNotExistOrIsHidden(): ViewAssertion = ViewAssertion { view, _ ->
        if (view != null && view.visibility == View.VISIBLE) {
            throw AssertionError("表示されないはずのビューが表示されている: $view")
        }
    }
}

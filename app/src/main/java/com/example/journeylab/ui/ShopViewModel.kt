package com.example.journeylab.ui

import androidx.lifecycle.LiveData
import androidx.lifecycle.MutableLiveData
import androidx.lifecycle.ViewModel
import com.example.journeylab.data.CartLine
import com.example.journeylab.data.Product
import java.util.Locale

/** カートの内容を Activity スコープで保持する。 */
class ShopViewModel : ViewModel() {

    private val _cart = MutableLiveData<List<CartLine>>(emptyList())
    val cart: LiveData<List<CartLine>> = _cart

    /** 注文番号はアプリ起動ごとに 0001 から連番。 */
    private var orderSequence = 0

    fun addToCart(product: Product) {
        val current = cartLines()
        val index = current.indexOfFirst { it.product.id == product.id }
        _cart.value = if (index >= 0) {
            current.toMutableList().also { it[index] = it[index].copy(quantity = it[index].quantity + 1) }
        } else {
            current + CartLine(product, 1)
        }
    }

    fun cartLines(): List<CartLine> = _cart.value.orEmpty()

    fun cartTotal(): Int = cartLines().sumOf { it.subtotal }

    /** 「注文する」ボタンを押せるかどうか。 */
    fun isCheckoutEnabled(): Boolean = cartLines().isNotEmpty()

    /** 注文を確定し、注文番号を返す。カートは空になる。 */
    fun placeOrder(): String {
        orderSequence += 1
        _cart.value = emptyList()
        return String.format(Locale.US, "ORDER-%04d", orderSequence)
    }
}

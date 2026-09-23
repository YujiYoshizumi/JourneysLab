package com.example.journeylab.data

data class CartLine(
    val product: Product,
    val quantity: Int,
) {
    val subtotal: Int get() = product.price * quantity
}

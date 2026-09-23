package com.example.journeylab.data

import java.util.Locale

/** 固定の商品データ（ネットワーク通信なし、インメモリ）。 */
data class Product(
    val id: String,
    val name: String,
    val price: Int,
)

object Catalog {

    val products: List<Product> = listOf(
        Product("P1", "ブルーマグカップ", 1280),
        Product("P2", "ノートブック A5", 880),
        Product("P3", "トートバッグ", 2200),
        Product("P4", "デスクライト", 4980),
    )

    fun byId(id: String): Product = products.first { it.id == id }
}

/** 価格表示は全画面で同じ書式（例: ¥1,280）にそろえる。 */
fun formatYen(amount: Int): String = String.format(Locale.US, "¥%,d", amount)

package com.example.journeylab.data

import org.junit.Assert.assertEquals
import org.junit.Test

/** 固定データと価格表記の単体テスト。 */
class CatalogTest {

    @Test
    fun catalogHasFourProducts() {
        assertEquals(4, Catalog.products.size)
        assertEquals(listOf("P1", "P2", "P3", "P4"), Catalog.products.map { it.id })
        assertEquals(
            listOf("ブルーマグカップ", "ノートブック A5", "トートバッグ", "デスクライト"),
            Catalog.products.map { it.name },
        )
    }

    @Test
    fun pricesAreFormattedWithAThousandsSeparator() {
        assertEquals("¥1,280", formatYen(1280))
        assertEquals("¥880", formatYen(880))
        assertEquals("¥2,200", formatYen(2200))
    }

    @Test
    fun cartLineSubtotalMultipliesPriceByQuantity() {
        assertEquals(4400, CartLine(Catalog.byId("P3"), quantity = 2).subtotal)
    }
}

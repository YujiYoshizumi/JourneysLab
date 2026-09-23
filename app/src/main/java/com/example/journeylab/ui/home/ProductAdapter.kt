package com.example.journeylab.ui.home

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.example.journeylab.data.Product
import com.example.journeylab.data.formatYen
import com.example.journeylab.databinding.ItemProductBinding

class ProductAdapter(
    private val onClick: (Product) -> Unit,
) : ListAdapter<Product, ProductAdapter.ViewHolder>(DIFF) {

    class ViewHolder(val binding: ItemProductBinding) : RecyclerView.ViewHolder(binding.root)

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val binding = ItemProductBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return ViewHolder(binding)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val product = getItem(position)
        holder.binding.productName.text = product.name
        holder.binding.productPrice.text = formatYen(product.price)
        holder.binding.productCard.contentDescription = product.name
        holder.binding.productCard.setOnClickListener { onClick(product) }
    }

    private companion object {
        val DIFF = object : DiffUtil.ItemCallback<Product>() {
            override fun areItemsTheSame(oldItem: Product, newItem: Product) = oldItem.id == newItem.id
            override fun areContentsTheSame(oldItem: Product, newItem: Product) = oldItem == newItem
        }
    }
}

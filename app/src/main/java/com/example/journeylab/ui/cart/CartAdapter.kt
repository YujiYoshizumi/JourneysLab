package com.example.journeylab.ui.cart

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.example.journeylab.R
import com.example.journeylab.data.CartLine
import com.example.journeylab.data.formatYen
import com.example.journeylab.databinding.ItemCartBinding

class CartAdapter : ListAdapter<CartLine, CartAdapter.ViewHolder>(DIFF) {

    class ViewHolder(val binding: ItemCartBinding) : RecyclerView.ViewHolder(binding.root)

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val binding = ItemCartBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return ViewHolder(binding)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val line = getItem(position)
        val context = holder.itemView.context
        holder.binding.cartItemName.text = line.product.name
        holder.binding.cartItemQuantity.text = context.getString(R.string.cart_quantity, line.quantity)
        holder.binding.cartItemSubtotal.text =
            context.getString(R.string.cart_subtotal, formatYen(line.subtotal))
    }

    private companion object {
        val DIFF = object : DiffUtil.ItemCallback<CartLine>() {
            override fun areItemsTheSame(oldItem: CartLine, newItem: CartLine) =
                oldItem.product.id == newItem.product.id

            override fun areContentsTheSame(oldItem: CartLine, newItem: CartLine) = oldItem == newItem
        }
    }
}

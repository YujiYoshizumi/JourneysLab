package com.example.journeylab.ui.cart

import android.os.Bundle
import android.view.View
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import androidx.recyclerview.widget.LinearLayoutManager
import com.example.journeylab.MainActivity
import com.example.journeylab.R
import com.example.journeylab.data.formatYen
import com.example.journeylab.databinding.FragmentCartBinding
import com.example.journeylab.ui.ShopViewModel
import com.example.journeylab.ui.order.OrderCompleteFragment

class CartFragment : Fragment(R.layout.fragment_cart) {

    private var _binding: FragmentCartBinding? = null
    private val binding get() = _binding!!

    private val viewModel: ShopViewModel by activityViewModels()
    private lateinit var adapter: CartAdapter

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        _binding = FragmentCartBinding.bind(view)

        adapter = CartAdapter()
        binding.cartList.layoutManager = LinearLayoutManager(requireContext())
        binding.cartList.adapter = adapter

        binding.checkoutButton.setOnClickListener {
            val orderNumber = viewModel.placeOrder()
            (requireActivity() as MainActivity).openScreen(
                OrderCompleteFragment.newInstance(orderNumber),
                OrderCompleteFragment.TAG,
            )
        }

        viewModel.cart.observe(viewLifecycleOwner) { render() }
    }

    override fun onResume() {
        super.onResume()
        (requireActivity() as MainActivity).configureToolbar(getString(R.string.cart_title), showShopMenu = false)
    }

    override fun onDestroyView() {
        _binding = null
        super.onDestroyView()
    }

    private fun render() {
        val binding = _binding ?: return
        val lines = viewModel.cartLines()
        adapter.submitList(lines)
        binding.cartEmptyText.visibility = if (lines.isEmpty()) View.VISIBLE else View.GONE
        binding.cartTotalText.text = getString(R.string.cart_total, formatYen(viewModel.cartTotal()))
        // 無効状態は Material Components の標準スタイルに任せる（独自の色指定はしない）。
        binding.checkoutButton.isEnabled = viewModel.isCheckoutEnabled()
    }

    companion object {
        const val TAG = "cart"
    }
}

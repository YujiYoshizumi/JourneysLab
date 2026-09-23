package com.example.journeylab.ui.detail

import android.os.Bundle
import android.view.View
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import com.example.journeylab.MainActivity
import com.example.journeylab.R
import com.example.journeylab.data.Catalog
import com.example.journeylab.data.Product
import com.example.journeylab.data.formatYen
import com.example.journeylab.databinding.FragmentProductDetailBinding
import com.example.journeylab.ui.ShopViewModel
import com.google.android.material.snackbar.Snackbar

class ProductDetailFragment : Fragment(R.layout.fragment_product_detail) {

    private var _binding: FragmentProductDetailBinding? = null
    private val binding get() = _binding!!

    private val viewModel: ShopViewModel by activityViewModels()
    private lateinit var product: Product

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        product = Catalog.byId(requireArguments().getString(ARG_PRODUCT_ID)!!)
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        _binding = FragmentProductDetailBinding.bind(view)

        binding.detailProductName.text = product.name
        binding.detailProductPrice.text = formatYen(product.price)
        binding.addToCartButton.setOnClickListener {
            viewModel.addToCart(product)
            Snackbar.make(requireView(), getString(R.string.detail_added_to_cart), Snackbar.LENGTH_LONG).show()
        }
    }

    override fun onResume() {
        super.onResume()
        (requireActivity() as MainActivity).configureToolbar(product.name, showShopMenu = true)
    }

    override fun onDestroyView() {
        _binding = null
        super.onDestroyView()
    }

    companion object {
        const val TAG = "detail"

        private const val ARG_PRODUCT_ID = "product_id"

        fun newInstance(productId: String): ProductDetailFragment = ProductDetailFragment().apply {
            arguments = Bundle().apply { putString(ARG_PRODUCT_ID, productId) }
        }
    }
}

package com.example.journeylab.ui.home

import android.os.Bundle
import android.view.View
import androidx.fragment.app.Fragment
import androidx.recyclerview.widget.LinearLayoutManager
import com.example.journeylab.MainActivity
import com.example.journeylab.R
import com.example.journeylab.data.Catalog
import com.example.journeylab.databinding.FragmentHomeBinding
import com.example.journeylab.ui.detail.ProductDetailFragment

class HomeFragment : Fragment(R.layout.fragment_home) {

    private var _binding: FragmentHomeBinding? = null
    private val binding get() = _binding!!

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        _binding = FragmentHomeBinding.bind(view)

        val adapter = ProductAdapter { product ->
            (requireActivity() as MainActivity).openScreen(
                ProductDetailFragment.newInstance(product.id),
                ProductDetailFragment.TAG,
            )
        }
        binding.productList.layoutManager = LinearLayoutManager(requireContext())
        binding.productList.adapter = adapter

        // 起動時、商品一覧は即座に表示する（ローディングやエラー表示は挟まない）。
        adapter.submitList(Catalog.products)
    }

    override fun onResume() {
        super.onResume()
        (requireActivity() as MainActivity).configureToolbar(getString(R.string.app_name), showShopMenu = true)
    }

    override fun onDestroyView() {
        _binding = null
        super.onDestroyView()
    }

    companion object {
        const val TAG = "home"
    }
}

package com.example.journeylab.ui.order

import android.os.Bundle
import android.view.View
import androidx.fragment.app.Fragment
import com.example.journeylab.MainActivity
import com.example.journeylab.R
import com.example.journeylab.databinding.FragmentOrderCompleteBinding

class OrderCompleteFragment : Fragment(R.layout.fragment_order_complete) {

    private var _binding: FragmentOrderCompleteBinding? = null
    private val binding get() = _binding!!

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        _binding = FragmentOrderCompleteBinding.bind(view)

        val orderNumber = requireArguments().getString(ARG_ORDER_NUMBER).orEmpty()
        binding.orderNumberText.text = getString(R.string.order_number, orderNumber)
        binding.backToHomeButton.setOnClickListener { (requireActivity() as MainActivity).goHome() }
    }

    override fun onResume() {
        super.onResume()
        (requireActivity() as MainActivity)
            .configureToolbar(getString(R.string.order_complete_title), showShopMenu = false)
    }

    override fun onDestroyView() {
        _binding = null
        super.onDestroyView()
    }

    companion object {
        const val TAG = "order_complete"

        private const val ARG_ORDER_NUMBER = "order_number"

        fun newInstance(orderNumber: String): OrderCompleteFragment = OrderCompleteFragment().apply {
            arguments = Bundle().apply { putString(ARG_ORDER_NUMBER, orderNumber) }
        }
    }
}

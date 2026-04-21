"""Tests for Savitzky-Golay filter and boundary detection."""

from __future__ import annotations

import numpy as np
import pytest

from prep.core.sg_filter import savitzky_golay_derivative, find_boundaries


class TestSavitzkyGolayDerivative:
    """Tests for the SG filter derivative computation."""

    def test_constant_signal_zero_derivative(self):
        """A flat signal should have zero derivative everywhere."""
        signal = np.array([0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8], dtype=np.float64)
        deriv = savitzky_golay_derivative(signal, window=5, poly_order=3, deriv_order=1)
        assert deriv.shape == signal.shape
        np.testing.assert_allclose(deriv, 0.0, atol=1e-10)

    def test_linear_signal_constant_derivative(self):
        """A linear signal should have constant first derivative."""
        signal = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0], dtype=np.float64)
        deriv = savitzky_golay_derivative(signal, window=5, poly_order=3, deriv_order=1)
        # Interior points should have derivative ~1.0
        np.testing.assert_allclose(deriv[2:-2], 1.0, atol=1e-10)

    def test_output_shape_matches_input(self):
        """Output array should have the same shape as input."""
        signal = np.random.rand(20)
        deriv = savitzky_golay_derivative(signal, window=5, poly_order=3, deriv_order=1)
        assert deriv.shape == signal.shape

    def test_short_signal_raises(self):
        """Signal shorter than window should raise ValueError."""
        signal = np.array([0.5, 0.6, 0.7])
        with pytest.raises(ValueError, match="Signal length"):
            savitzky_golay_derivative(signal, window=5, poly_order=3, deriv_order=1)


class TestFindBoundaries:
    """Tests for topic boundary detection."""

    def test_clear_dips_detected(self):
        """Obvious similarity dips should be detected as boundaries."""
        similarities = np.array([
            0.9, 0.85, 0.88, 0.87,
            0.3,
            0.9, 0.88, 0.86, 0.89,
            0.25,
            0.91, 0.87, 0.90,
        ], dtype=np.float64)
        bounds = find_boundaries(similarities, percentile_threshold=20.0, min_distance=2)
        assert len(bounds) >= 2
        assert any(3 <= b <= 5 for b in bounds), f"Expected boundary near 4, got {bounds}"
        assert any(8 <= b <= 10 for b in bounds), f"Expected boundary near 9, got {bounds}"

    def test_flat_signal_no_boundaries(self):
        """A flat similarity signal should produce no boundaries."""
        similarities = np.array([0.85, 0.86, 0.84, 0.85, 0.86, 0.85, 0.84], dtype=np.float64)
        bounds = find_boundaries(similarities, percentile_threshold=20.0, min_distance=2)
        assert len(bounds) == 0

    def test_min_distance_enforced(self):
        """Boundaries closer than min_distance should be filtered."""
        similarities = np.array([
            0.9, 0.9, 0.2, 0.2, 0.9, 0.9, 0.9, 0.9,
        ], dtype=np.float64)
        bounds = find_boundaries(similarities, percentile_threshold=30.0, min_distance=2)
        assert len(bounds) <= 1

    def test_short_signal_uses_percentile_fallback(self):
        """Signals with < 5 values should use percentile-only method."""
        similarities = np.array([0.9, 0.3, 0.9], dtype=np.float64)
        bounds = find_boundaries(similarities, percentile_threshold=30.0, min_distance=1)
        assert 1 in bounds

    def test_empty_signal_returns_empty(self):
        """Empty similarity array should return no boundaries."""
        bounds = find_boundaries(np.array([], dtype=np.float64))
        assert bounds == []

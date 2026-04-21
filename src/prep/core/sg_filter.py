"""
Savitzky-Golay filter for semantic boundary detection.

Implements the SG filter using Vandermonde matrices and least-squares.
Used to smooth similarity signals and compute derivatives for
finding topic boundaries in text.
"""

from __future__ import annotations

import math
from typing import List

import numpy as np


def savitzky_golay_derivative(
    signal: np.ndarray,
    window: int = 5,
    poly_order: int = 3,
    deriv_order: int = 1,
) -> np.ndarray:
    """Apply Savitzky-Golay filter and return the nth derivative of the signal.

    Args:
        signal: 1D input signal array.
        window: Filter window size (must be odd, >= poly_order + 1).
        poly_order: Polynomial order for local fitting.
        deriv_order: Derivative order (0 = smoothing, 1 = first derivative).

    Returns:
        Filtered/differentiated signal of same shape as input.

    Raises:
        ValueError: If signal is shorter than window or parameters are invalid.
    """
    if len(signal) < window:
        raise ValueError(
            f"Signal length ({len(signal)}) must be >= window ({window})"
        )
    if window % 2 == 0:
        raise ValueError("Window must be odd")
    if poly_order >= window:
        raise ValueError("poly_order must be < window")

    half = window // 2
    # Build Vandermonde matrix for indices [-half, ..., 0, ..., half]
    indices = np.arange(-half, half + 1, dtype=np.float64)
    vander = np.vander(indices, N=poly_order + 1, increasing=True)

    # Least-squares solution: coeffs = (V^T V)^{-1} V^T
    coeffs = np.linalg.lstsq(vander, np.eye(window), rcond=None)[0]
    kernel = coeffs[deriv_order] * math.factorial(deriv_order)

    # Pad signal with reflected edges to avoid boundary artifacts, then trim
    padded = np.pad(signal, half, mode="reflect")
    convolved = np.convolve(padded, kernel[::-1], mode="same")
    result = convolved[half:-half] if half > 0 else convolved
    return result


def find_boundaries(
    similarities: np.ndarray,
    percentile_threshold: float = 20.0,
    min_distance: int = 2,
) -> List[int]:
    """Find topic boundaries in a similarity signal.

    Uses Savitzky-Golay filtering to find zero-crossings of the first
    derivative (local minima in similarity = topic shifts), filtered by
    a percentile threshold on raw similarity values.

    For short signals (< 5 values), falls back to simple percentile-based
    boundary detection.

    Args:
        similarities: Array of pairwise cosine similarities between adjacent items.
        percentile_threshold: Only keep boundaries where raw similarity
            is below this percentile (default 20th = genuinely low).
        min_distance: Minimum gap between boundaries.

    Returns:
        Sorted list of boundary indices.
    """
    if len(similarities) == 0:
        return []

    threshold = float(np.percentile(similarities, percentile_threshold))

    if len(similarities) < 5:
        bounds = [i for i in range(len(similarities)) if similarities[i] <= threshold]
        return _enforce_min_distance(bounds, min_distance)

    try:
        derivative = savitzky_golay_derivative(
            similarities, window=5, poly_order=3, deriv_order=1
        )
    except (ValueError, np.linalg.LinAlgError):
        bounds = [i for i in range(len(similarities)) if similarities[i] <= threshold]
        return _enforce_min_distance(bounds, min_distance)

    minima = []
    for i in range(1, len(derivative)):
        if derivative[i - 1] < 0 and derivative[i] >= 0:
            minima.append(i)

    bounds = [m for m in minima if m < len(similarities) and similarities[m] <= threshold]
    return _enforce_min_distance(bounds, min_distance)


def _enforce_min_distance(bounds: List[int], min_distance: int) -> List[int]:
    """Filter boundaries to enforce minimum distance between them."""
    if not bounds or min_distance <= 0:
        return bounds
    filtered = [bounds[0]]
    for b in bounds[1:]:
        if b - filtered[-1] >= min_distance:
            filtered.append(b)
    return filtered

"""Resolution-independent raster spatial queries."""

from __future__ import annotations

from typing import Any

import numpy as np
from PIL import Image as PilImage

_VALUE_RASTER_DIMENSIONS = 2


def _resample(
    array: np.ndarray, target_shape: tuple[int, int], mode: str
) -> np.ndarray:
    """Resample a normalized-map raster to ``(height, width)``."""
    if array.shape == target_shape:
        return array
    height, width = target_shape
    if mode == "discrete":
        y_indices = np.minimum(
            (np.arange(height) * array.shape[0] / height).astype(int),
            array.shape[0] - 1,
        )
        x_indices = np.minimum(
            (np.arange(width) * array.shape[1] / width).astype(int),
            array.shape[1] - 1,
        )
        return array[np.ix_(y_indices, x_indices)]

    image = PilImage.fromarray(array.astype(np.float32), mode="F")
    resized = image.resize((width, height), PilImage.Resampling.BILINEAR)
    return np.array(resized, dtype=np.float32)


def compute_resampled_query(
    arrays: list[np.ndarray],
    modes: list[str],
    conditions: list[dict[str, Any]],
) -> np.ndarray:
    """Evaluate conditions after resampling layers to the largest grid."""
    if not arrays or len(arrays) != len(modes):
        raise ValueError("Query requires matching raster arrays and modes")
    if any(array.ndim != _VALUE_RASTER_DIMENSIONS for array in arrays):
        raise ValueError("Only value rasters can be queried")

    target_shape = (
        max(array.shape[0] for array in arrays),
        max(array.shape[1] for array in arrays),
    )
    normalized = [
        _resample(array, target_shape, mode)
        for array, mode in zip(arrays, modes)
    ]
    mask = np.ones(target_shape, dtype=np.bool_)
    for condition in conditions:
        index = int(condition["index"])
        if index < 0 or index >= len(normalized):
            raise ValueError(f"Invalid raster query index: {index}")
        array = normalized[index]
        operator = str(condition["op"])
        if operator == "between":
            mask &= (array >= float(condition["min"])) & (
                array <= float(condition["max"])
            )
            continue
        value = float(condition["value"])
        comparisons = {
            "eq": array == value,
            "neq": array != value,
            "gt": array > value,
            "lt": array < value,
            "gte": array >= value,
            "lte": array <= value,
        }
        if operator not in comparisons:
            raise ValueError(f"Unknown raster query operator: {operator}")
        mask &= comparisons[operator]
    return mask

"""
JSON serialization and optional follow-lane metrics for UFLD lane polylines.

Used by lane_zmq_publisher and any robot consumer expecting schema_version 1.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

LANE_JSON_SCHEMA_VERSION = 1

# Point = (x, y) in pixel coordinates, original frame space
LanePolyline = Sequence[Tuple[Union[int, float], Union[int, float]]]
Lanes = Sequence[LanePolyline]


def polylines_to_json_lanes(lanes: Lanes) -> List[Dict[str, Any]]:
    """Convert UFLD `lanes` list-of-polylines to JSON-serializable lane objects."""
    out: List[Dict[str, Any]] = []
    for i, poly in enumerate(lanes):
        pts: List[List[float]] = []
        for p in poly:
            if len(p) >= 2:
                pts.append([float(p[0]), float(p[1])])
        out.append({"id": i, "points": pts})
    return out


def compute_tracking_metrics(
    lanes: Lanes,
    image_width: int,
    image_height: int,
    bottom_band_ratio: float = 0.35,
) -> Optional[Dict[str, Any]]:
    """
    Derive simple follow-lane metrics from detected polylines.

    Uses points in the bottom band of the image (y >= height * (1 - bottom_band_ratio)).
    If at least two x samples exist, treats min/max x as lane boundaries at the bottom
    and sets target_x to the midpoint. center_offset_px = target_x - image_center_x.

    Returns None if insufficient points.
    """
    if image_width <= 0 or image_height <= 0:
        return None

    y_min = image_height * (1.0 - bottom_band_ratio)
    xs: List[float] = []
    ys: List[float] = []
    for poly in lanes:
        for p in poly:
            if len(p) < 2:
                continue
            x, y = float(p[0]), float(p[1])
            if y >= y_min:
                xs.append(x)
                ys.append(y)

    if len(xs) < 2:
        return {
            "center_offset_px": None,
            "target_x": None,
            "image_center_x": image_width / 2.0,
            "lane_half_width_px": None,
            "bottom_y_mean": float(sum(ys) / len(ys)) if ys else None,
            "num_points_bottom_band": len(xs),
        }

    xmin, xmax = min(xs), max(xs)
    target_x = (xmin + xmax) / 2.0
    center_x = image_width / 2.0
    return {
        "center_offset_px": float(target_x - center_x),
        "target_x": float(target_x),
        "image_center_x": float(center_x),
        "lane_half_width_px": float((xmax - xmin) / 2.0),
        "bottom_y_mean": float(sum(ys) / len(ys)) if ys else None,
        "num_points_bottom_band": len(xs),
    }


def build_lane_frame_payload(
    lanes: Lanes,
    frame_id: int,
    image_width: int,
    image_height: int,
    *,
    timestamp: Optional[float] = None,
    include_tracking: bool = True,
) -> Dict[str, Any]:
    """
    Build one JSON-serializable dict per frame (schema_version 1).

    timestamp: defaults to time.time() (wall clock, seconds).
    """
    ts = time.time() if timestamp is None else timestamp
    payload: Dict[str, Any] = {
        "schema_version": LANE_JSON_SCHEMA_VERSION,
        "timestamp": float(ts),
        "frame_id": int(frame_id),
        "image": {"width": int(image_width), "height": int(image_height)},
        "lanes": polylines_to_json_lanes(lanes),
    }
    if include_tracking:
        tr = compute_tracking_metrics(lanes, image_width, image_height)
        payload["tracking"] = tr if tr is not None else {}
    else:
        payload["tracking"] = None
    return payload

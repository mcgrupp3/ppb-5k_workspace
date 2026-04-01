#!/usr/bin/env python3
"""
Pi5: run in-process UFLD lane detection and publish per-frame JSON over ZMQ PUB.

Requires hailo-apps env (e.g. ``source vision_scripts/hailo-apps/setup_env.sh``) on the device.

Transport: same pattern as ``robot_scripts/src/working_code/zmq_test.py``, default bind
``tcp://*:5556``. Sends with ``zmq.NOBLOCK``; if the socket buffer fills, frames are dropped
and a drop counter increments (no backpressure on inference).

With ``--zmq-topic``, messages are multipart ``[topic_utf8, json_utf8]`` so SUB clients can
filter by topic; otherwise uses ``send_json`` (equivalent to topic ``""`` for SUB).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, List, Optional

import zmq


def _bootstrap_sys_path() -> None:
    """Resolve ``hailo_apps``, ``lane_detection`` script dir, and this ``vision`` dir."""
    vision_dir = Path(__file__).resolve().parent
    if str(vision_dir) not in sys.path:
        sys.path.insert(0, str(vision_dir))

    for repo in Path(__file__).resolve().parents:
        if (repo / "hailo_apps" / "config" / "config_manager.py").exists():
            lane_dir = repo / "hailo_apps" / "python" / "standalone_apps" / "lane_detection"
            sys.path.insert(0, str(lane_dir))
            sys.path.insert(0, str(repo))
            return

    raise RuntimeError(
        "Could not find hailo-apps checkout (hailo_apps/config/config_manager.py). "
        "Clone the repo or run from the workspace that contains vision_scripts/hailo-apps."
    )


_bootstrap_sys_path()

from lane_json import build_lane_frame_payload  # noqa: E402

# Import after path bootstrap (Hailo + lane_detection live under hailo-apps).
from hailo_apps.python.core.common.hailo_logger import get_logger, init_logging, level_from_args  # noqa: E402
from hailo_apps.python.core.common.core import handle_and_resolve_args  # noqa: E402

import lane_detection as ld  # noqa: E402

logger = get_logger(__name__)


def _make_zmq_sender(
    socket: zmq.Socket,
    topic: str,
) -> tuple[Callable[[dict[str, Any]], None], List[int]]:
    """
    Returns (send_fn, drops_ref) where drops_ref[0] is the number of dropped sends
    due to zmq.Again (NOBLOCK full buffer).
    """
    drops: List[int] = [0]
    use_multipart = bool(topic)

    def send_payload(payload: dict[str, Any]) -> None:
        try:
            if use_multipart:
                socket.send_multipart(
                    [topic.encode("utf-8"), json.dumps(payload).encode("utf-8")],
                    flags=zmq.NOBLOCK,
                )
            else:
                socket.send_json(payload, flags=zmq.NOBLOCK)
        except zmq.Again:
            drops[0] += 1

    return send_payload, drops


def main() -> None:
    parser = ld.build_argument_parser()
    parser.description = "UFLD lane inference + ZMQ JSON publisher (Pi5 → Pi4 / consumers)."
    parser.add_argument(
        "--zmq-bind",
        type=str,
        default="tcp://*:5556",
        help='ZMQ PUB bind address (default: tcp://*:5556; use a different port than zmq_test.py 5555).',
    )
    parser.add_argument(
        "--zmq-topic",
        type=str,
        default="",
        help='Optional topic string; if set, send multipart [topic, json]. Empty uses send_json.',
    )
    parser.add_argument(
        "--no-tracking",
        action="store_true",
        help="Omit derived follow-lane fields in JSON (center_offset_px, target_x, ...).",
    )
    args = parser.parse_args()

    init_logging(level=level_from_args(args))
    handle_and_resolve_args(args, ld.APP_NAME)

    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)

    if args.show:
        if sys.platform != "win32" and not os.environ.get("DISPLAY"):
            logger.warning(
                "DISPLAY is not set — cv2.imshow may not work over plain SSH. "
                "Use desktop, export DISPLAY=:0, X11 forward, or VNC."
            )

    try:
        cap, images, input_type, original_frame_width, original_frame_height, total_frames = (
            ld.resolve_capture_and_metadata(args.input, 1)
        )
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)

    ufld_processing = ld.UFLDProcessing(
        num_cell_row=100,
        num_cell_col=100,
        num_row=56,
        num_col=41,
        num_lanes=4,
        crop_ratio=0.8,
        original_frame_width=original_frame_width,
        original_frame_height=original_frame_height,
        total_frames=total_frames if total_frames is not None else 0,
    )

    ctx = zmq.Context()
    pub = ctx.socket(zmq.PUB)
    pub.bind(args.zmq_bind)
    send_payload, drops = _make_zmq_sender(pub, args.zmq_topic)
    logger.info(
        "ZMQ PUB bound to %s; topic=%r; NOBLOCK send (drops if consumer is slow).",
        args.zmq_bind,
        args.zmq_topic or "(send_json)",
    )

    def on_lane_frame(lanes: list, frame_id: int, width: int, height: int) -> None:
        payload = build_lane_frame_payload(
            lanes,
            frame_id,
            width,
            height,
            include_tracking=not args.no_tracking,
        )
        send_payload(payload)

    ld.run_inference_pipeline(
        cap,
        images,
        input_type,
        args.hef_path,
        batch_size=1,
        output_dir=args.output_dir or os.path.join(os.getcwd(), "output"),
        ufld_processing=ufld_processing,
        total_frames=total_frames,
        show_preview=args.show,
        preview_swap_rb=(
            args.show
            and (not args.no_preview_swap_rb)
            and (input_type == "rpi")
        ),
        write_video=False,
        on_lane_frame=on_lane_frame,
    )

    if drops[0]:
        logger.warning("ZMQ dropped %d frames (send buffer full / slow subscriber).", drops[0])
    pub.close(0)
    ctx.term()


if __name__ == "__main__":
    main()

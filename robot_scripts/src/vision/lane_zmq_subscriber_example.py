#!/usr/bin/env python3
"""
Pi4 / laptop: minimal ZMQ SUB example for lane JSON streamed from ``lane_zmq_publisher.py``.

Usage (replace with your Pi5 LAN IP)::

    python3 lane_zmq_subscriber_example.py --connect tcp://192.168.1.50:5556

If the publisher was started with ``--zmq-topic lanes``, use::

    python3 lane_zmq_subscriber_example.py --connect tcp://192.168.1.50:5556 --topic lanes --multipart

Requires: ``pip install pyzmq`` (same as the publisher).
"""
from __future__ import annotations

import argparse
import json
import sys

import zmq


def main() -> None:
    p = argparse.ArgumentParser(description="Subscribe to lane JSON from Pi5 lane_zmq_publisher.")
    p.add_argument(
        "--connect",
        "-c",
        type=str,
        required=True,
        help="SUB connect URL, e.g. tcp://PI5_IP:5556 (must match publisher --zmq-bind port).",
    )
    p.add_argument(
        "--topic",
        type=str,
        default="",
        help="Subscription prefix; must match publisher --zmq-topic (empty for send_json mode).",
    )
    p.add_argument(
        "--multipart",
        action="store_true",
        help="Decode multipart [topic, json] frames (use when publisher sets --zmq-topic).",
    )
    args = p.parse_args()

    ctx = zmq.Context()
    socket = ctx.socket(zmq.SUB)
    socket.connect(args.connect)
    socket.setsockopt_string(zmq.SUBSCRIBE, args.topic)

    print(f"Connected SUB to {args.connect!r}, subscribe={args.topic!r}, multipart={args.multipart}", file=sys.stderr)

    try:
        while True:
            if args.multipart:
                parts = socket.recv_multipart()
                if len(parts) < 2:
                    continue
                data = json.loads(parts[1].decode("utf-8"))
            else:
                data = socket.recv_json()
            print(json.dumps(data, indent=2))
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
    finally:
        socket.close(0)
        ctx.term()


if __name__ == "__main__":
    main()

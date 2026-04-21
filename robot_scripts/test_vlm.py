#!/usr/bin/env python3
"""
End-to-end test: capture one frame from the CSI camera and run Qwen2-VL inference.
Run on Pi 5 HOST (not in Docker).

Usage:
    HAILO_APPS_ROOT=/path/to/hailo-apps python3 test_inference.py
    # or set the constant below directly
"""

import os
import sys
import time
import cv2
from pathlib import Path

# ── Fill this in if not setting via environment ──────────────────────────────
HAILO_APPS_ROOT = os.environ.get("HAILO_APPS_ROOT", "/home/vittoria/ppb-5k_workspace/vision_scripts/hailo-apps/hailo_apps/python/gen_ai_apps/vlm_chat")
# ─────────────────────────────────────────────────────────────────────────────

TEST_PROMPT = "Describe what you see in this image in one or two sentences."
WARMUP_FRAMES = 15   # frames discarded so AGC/AWB can settle
INFERENCE_TIMEOUT = 60


def bootstrap():
    root = Path(HAILO_APPS_ROOT).resolve()
    if not (root / "hailo_apps").is_dir():
        print(f"[FAIL] HAILO_APPS_ROOT doesn't look right: {root}")
        print("       Set the constant at the top of this script or export HAILO_APPS_ROOT=...")
        sys.exit(1)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    print(f"[OK] hailo-apps root: {root}")


def capture_frame():
    from picamera2 import Picamera2
    from hailo_apps.python.gen_ai_apps.vlm_chat.backend import Backend  # type: ignore

    print(f"Warming up camera ({WARMUP_FRAMES} frames)...")
    cam = Picamera2()
    config = cam.create_preview_configuration(
        main={"size": (640, 480), "format": "RGB888"}
    )
    cam.configure(config)
    cam.start()

    try:
        raw = None
        for i in range(WARMUP_FRAMES + 1):
            raw = cam.capture_array()
        if raw is None:
            raise RuntimeError("Camera returned no frames")
    finally:
        cam.stop()
        cam.close()

    # Match the preprocessing the Backend expects
    rgb = Backend.convert_resize_image(raw)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    print(f"[OK] Frame captured — shape: {bgr.shape}, dtype: {bgr.dtype}")
    return bgr


def run_inference(bgr):
    from hailo_apps.python.gen_ai_apps.vlm_chat.backend import Backend          # type: ignore
    from hailo_apps.python.core.common.core import resolve_hef_path              # type: ignore
    from hailo_apps.python.core.common.defines import HAILO10H_ARCH, VLM_CHAT_APP  # type: ignore

    hef_path = resolve_hef_path(None, app_name=VLM_CHAT_APP, arch=HAILO10H_ARCH)
    if hef_path is None:
        print("[FAIL] Could not resolve HEF path — is the model downloaded?")
        sys.exit(1)
    print(f"[OK] HEF resolved: {hef_path}")

    print("Initialising backend (this may take a few seconds)...")
    t0 = time.time()
    backend = Backend(
        hef_path=str(hef_path),
        max_tokens=200,
        temperature=0.1,
        seed=42,
        system_prompt="You are a helpful assistant that analyzes images and answers questions about them.",
    )
    print(f"[OK] Backend ready in {time.time() - t0:.1f}s")

    print(f"\nPrompt: {TEST_PROMPT!r}")
    print("Running inference...\n")
    t1 = time.time()
    result = backend.vlm_inference(bgr, TEST_PROMPT, INFERENCE_TIMEOUT)
    elapsed = time.time() - t1

    backend.close()
    return result, elapsed


if __name__ == "__main__":
    print("=== Pi 5 Inference Test ===\n")

    bootstrap()
    bgr = capture_frame()
    result, elapsed = run_inference(bgr)

    print(f"\n--- Result ({elapsed:.1f}s) ---")
    print(result.get("answer", result))
    print("\n=== Test complete ===")
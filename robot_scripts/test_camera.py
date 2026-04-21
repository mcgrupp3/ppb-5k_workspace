#!/usr/bin/env python3
"""
Quick camera verification script for Pi 5 CSI camera.
Run on Pi 5 HOST (not in Docker).

Usage:
    python3 test_camera.py
"""

import sys
import time

def check_picamera2():
    try:
        from picamera2 import Picamera2
        print("[OK] picamera2 imported successfully")
        return Picamera2
    except ImportError as e:
        print(f"[FAIL] picamera2 not found: {e}")
        print("       Install with: sudo apt install -y python3-picamera2")
        sys.exit(1)

def check_camera_detected(Picamera2):
    cameras = Picamera2.global_camera_info()
    if not cameras:
        print("[FAIL] No cameras detected")
        print("       Check: vcgencmd get_camera  (should show 'detected=1')")
        print("       Check: libcamera-hello --list-cameras")
        sys.exit(1)
    print(f"[OK] {len(cameras)} camera(s) detected:")
    for i, cam in enumerate(cameras):
        print(f"       [{i}] {cam}")
    return cameras

def capture_test_frame(Picamera2, output_path="/home/pi/camera_test.jpg"):
    print("\nCapturing test frame...")
    cam = Picamera2()

    # Still config: highest quality single capture
    config = cam.create_still_configuration(
        main={"size": (1280, 720)},
        display=None
    )
    cam.configure(config)

    cam.start()
    time.sleep(1)  # Let the sensor settle (AGC, AWB)

    cam.capture_file(output_path)
    cam.stop()
    cam.close()

    print(f"[OK] Frame captured: {output_path}")
    return output_path

def check_output(path):
    import os
    if not os.path.exists(path):
        print(f"[FAIL] File not found at {path}")
        sys.exit(1)
    size = os.path.getsize(path)
    if size < 1000:
        print(f"[FAIL] File is suspiciously small ({size} bytes) — likely a blank/corrupt frame")
        sys.exit(1)
    print(f"[OK] File size: {size / 1024:.1f} KB — looks healthy")

if __name__ == "__main__":
    print("=== Pi 5 Camera Verification ===\n")

    Picamera2 = check_picamera2()
    check_camera_detected(Picamera2)

    output = "./camera_test.jpg"
    capture_test_frame(Picamera2, output)
    check_output(output)

    print("\n=== All checks passed! ===")
    print(f"Review the image: scp pi@<pi5-ip>:{output} .")
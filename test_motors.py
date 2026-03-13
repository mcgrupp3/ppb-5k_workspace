#!/usr/bin/env python3
"""
Motor Test Script - Mecanum Robot
Sends velocity commands to Pico over UART to verify motor behavior.
Run directly on Pi 4, no ROS required.
"""

import struct
import time
import serial

# ── Config ────────────────────────────────────────────────────────────────────
UART_PORT = '/dev/ttyAMA3'
UART_BAUD = 115200
TEST_SPEED = 0.3   # 30% — safe for bench testing
TEST_DURATION = 3  # seconds per test


# ── Pico UART ─────────────────────────────────────────────────────────────────
class PicoSerial:
    def __init__(self, port, baud):
        self.ser = serial.Serial(port, baud, timeout=0)
        print(f"✓ Opened {port} at {baud} baud")

    def send(self, vx, vy, omega):
        vx_i    = int(max(-100, min(100, vx    * 100)))
        vy_i    = int(max(-100, min(100, vy    * 100)))
        omega_i = int(max(-100, min(100, omega * 100)))
        chk = (vx_i + vy_i + omega_i) & 0xFF
        packet = bytes([0xFF, vx_i & 0xFF, vy_i & 0xFF, omega_i & 0xFF, chk])
        self.ser.write(packet)

    def stop(self):
        self.send(0.0, 0.0, 0.0)

    def close(self):
        self.stop()
        self.ser.close()


# ── Test helpers ──────────────────────────────────────────────────────────────
def run(pico, label, vx=0.0, vy=0.0, omega=0.0, duration=TEST_DURATION):
    print(f"\n  → {label}")
    end = time.time() + duration
    while time.time() < end:
        pico.send(vx, vy, omega)
        time.sleep(0.1)  # send every 100ms, well within 500ms watchdog
    pico.stop()
    time.sleep(0.5)


def section(title):
    print(f"\n{'=' * 50}")
    print(f"  {title}")
    print('=' * 50)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 50)
    print("  MECANUM MOTOR TEST — UART → PICO")
    print("=" * 50)
    print(f"\n  Port:       {UART_PORT}")
    print(f"  Speed:      {int(TEST_SPEED * 100)}%")
    print(f"  Duration:   {TEST_DURATION}s per test")
    print("\n  Make sure wheels are off the ground!")
    input("\n  Press ENTER to start...\n")

    pico = PicoSerial(UART_PORT, UART_BAUD)

    try:
        # ── Test 1: Cardinal directions ───────────────────────────────────────
        section("TEST 1: Cardinal Directions")
        run(pico, "Forward",   vx= TEST_SPEED)
        run(pico, "Backward",  vx=-TEST_SPEED)
        run(pico, "Strafe right", vy= TEST_SPEED)
        run(pico, "Strafe left",  vy=-TEST_SPEED)

        # ── Test 2: Rotation ──────────────────────────────────────────────────
        section("TEST 2: Rotation")
        run(pico, "Rotate clockwise",        omega=-TEST_SPEED)
        run(pico, "Rotate counter-clockwise", omega= TEST_SPEED)

        # ── Test 3: Diagonal (mecanum sanity check) ───────────────────────────
        section("TEST 3: Diagonal Movement")
        run(pico, "Diagonal forward-right", vx= TEST_SPEED, vy= TEST_SPEED)
        run(pico, "Diagonal forward-left",  vx= TEST_SPEED, vy=-TEST_SPEED)
        run(pico, "Diagonal back-right",    vx=-TEST_SPEED, vy= TEST_SPEED)
        run(pico, "Diagonal back-left",     vx=-TEST_SPEED, vy=-TEST_SPEED)

        # ── Test 4: Higher speed ──────────────────────────────────────────────
        section("TEST 4: Higher Speed (60%)")
        run(pico, "Forward at 60%", vx=0.6, duration=2)
        run(pico, "Backward at 60%", vx=-0.6, duration=2)

        print("\n" + "=" * 50)
        print("  ALL TESTS COMPLETE ✓")
        print("=" * 50)
        print("\n  What to check:")
        print("  - Forward: all 4 wheels spin same direction")
        print("  - Strafe:  front/back pairs spin opposite directions")
        print("  - Rotate:  left/right sides spin opposite directions")
        print("  - Any wheel not spinning → check Pico pin assignments")
        print("  - Wrong direction → flip IN1/IN2 for that motor in main.py")

    except KeyboardInterrupt:
        print("\n\n  *** INTERRUPTED ***")
    finally:
        print("\n  Stopping motors...")
        pico.close()
        print("  Done.")


if __name__ == '__main__':
    main()
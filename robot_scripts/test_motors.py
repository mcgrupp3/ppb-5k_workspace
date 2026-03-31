# #!/usr/bin/env python3
# """
# Motor Test Script - Mecanum Robot
# Drives motors directly via GPIO to L298N drivers.
# Run directly on Pi 4, no ROS or Pico required.
# """

# import time
# import RPi.GPIO as GPIO

# # ── Pin config ────────────────────────────────────────────────────────────────
# # Left board
# FL_ENA = 12   # PWM0 - FL speed
# FL_IN1 =  7   # FL forward
# FL_IN2 = 16   # FL backward
# BL_ENB = 13   # PWM1 - BL speed
# BL_IN3 =  6   # BL forward
# BL_IN4 =  5   # BL backward

# # Right board
# FR_ENA = 18   # PWM0 - FR speed
# FR_IN1 = 15   # FR forward
# FR_IN2 = 14   # FR backward
# BR_ENB = 19   # PWM1 - BR speed
# BR_IN3 = 20   # BR forward
# BR_IN4 = 21   # BR backward

# PWM_FREQ     = 1000   # Hz
# TEST_SPEED   = 30     # % duty cycle — safe for bench testing
# TEST_DURATION = 3     # seconds per test


# # ── GPIO setup ────────────────────────────────────────────────────────────────
# class Motors:
#     def __init__(self):
#         GPIO.setmode(GPIO.BCM)
#         GPIO.setwarnings(False)

#         self.dir_pins = [
#             FL_IN1, FL_IN2,
#             BL_IN3, BL_IN4,
#             FR_IN1, FR_IN2,
#             BR_IN3, BR_IN4,
#         ]
#         GPIO.setup(self.dir_pins, GPIO.OUT, initial=GPIO.LOW)

#         pwm_pins = [FL_ENA, BL_ENB, FR_ENA, BR_ENB]
#         GPIO.setup(pwm_pins, GPIO.OUT, initial=GPIO.LOW)

#         self.pwm = {
#             'fl': GPIO.PWM(FL_ENA, PWM_FREQ),
#             'bl': GPIO.PWM(BL_ENB, PWM_FREQ),
#             'fr': GPIO.PWM(FR_ENA, PWM_FREQ),
#             'br': GPIO.PWM(BR_ENB, PWM_FREQ),
#         }
#         for p in self.pwm.values():
#             p.start(0)

#         print("✓ GPIO ready")

#     def _motor(self, in_a, in_b, pwm, speed):
#         """Set one motor. speed: -100 to 100"""
#         if speed > 0:
#             GPIO.output(in_a, GPIO.HIGH)
#             GPIO.output(in_b, GPIO.LOW)
#         elif speed < 0:
#             GPIO.output(in_a, GPIO.LOW)
#             GPIO.output(in_b, GPIO.HIGH)
#         else:
#             GPIO.output(in_a, GPIO.LOW)
#             GPIO.output(in_b, GPIO.LOW)
#         pwm.ChangeDutyCycle(min(100, abs(speed)))

#     def set(self, fl, fr, bl, br):
#         self._motor(FL_IN1, FL_IN2, self.pwm['fl'], fl)
#         self._motor(FR_IN1, FR_IN2, self.pwm['fr'], -fr)  # inverted — motor faces opposite direction
#         self._motor(BL_IN3, BL_IN4, self.pwm['bl'], bl)
#         self._motor(BR_IN3, BR_IN4, self.pwm['br'], -br)  # inverted — motor faces opposite direction

#     def mecanum(self, vx, vy, omega):
#         """
#         vx:    forward/backward  (+forward)
#         vy:    strafe            (+right)
#         omega: rotation          (+clockwise)
#         All values -100 to 100
#         """
#         fl = vx - vy - omega
#         fr = vx + vy + omega
#         bl = vx + vy - omega
#         br = vx - vy + omega

#         # Scale if any value exceeds 100
#         mx = max(abs(fl), abs(fr), abs(bl), abs(br), 1)
#         if mx > 100:
#             fl, fr, bl, br = [v * 100 / mx for v in (fl, fr, bl, br)]

#         self.set(fl, fr, bl, br)

#     def stop(self):
#         self.set(0, 0, 0, 0)

#     def cleanup(self):
#         self.stop()
#         for p in self.pwm.values():
#             p.stop()
#         GPIO.cleanup()


# # ── Test helpers ──────────────────────────────────────────────────────────────
# def run(motors, label, vx=0, vy=0, omega=0, duration=TEST_DURATION):
#     print(f"\n  → {label}")
#     motors.mecanum(vx, vy, omega)
#     time.sleep(duration)
#     motors.stop()
#     time.sleep(0.5)


# def section(title):
#     print(f"\n{'=' * 50}")
#     print(f"  {title}")
#     print('=' * 50)


# # ── Main ──────────────────────────────────────────────────────────────────────
# def main():
#     S = TEST_SPEED
#     print("=" * 50)
#     print("  MECANUM MOTOR TEST — DIRECT GPIO")
#     print("=" * 50)
#     print(f"\n  Speed:    {S}%")
#     print(f"  Duration: {TEST_DURATION}s per test")
#     print("\n  Make sure wheels are off the ground!")
#     input("\n  Press ENTER to start...\n")

#     motors = Motors()

#     try:
#         section("TEST 1: Cardinal Directions")
#         run(motors, "Forward",       vx= S)
#         run(motors, "Backward",      vx=-S)
#         run(motors, "Strafe right",  vy= S)
#         run(motors, "Strafe left",   vy=-S)

#         section("TEST 2: Rotation")
#         run(motors, "Rotate clockwise",         omega= S)
#         run(motors, "Rotate counter-clockwise", omega=-S)

#         section("TEST 3: Diagonal Movement")
#         run(motors, "Diagonal forward-right", vx= S, vy= S)
#         run(motors, "Diagonal forward-left",  vx= S, vy=-S)
#         run(motors, "Diagonal back-right",    vx=-S, vy= S)
#         run(motors, "Diagonal back-left",     vx=-S, vy=-S)

#         section("TEST 4: Higher Speed (60%)")
#         run(motors, "Forward at 60%",  vx= 60, duration=2)
#         run(motors, "Backward at 60%", vx=-60, duration=2)

#         print("\n" + "=" * 50)
#         print("  ALL TESTS COMPLETE ✓")
#         print("=" * 50)
#         print("\n  What to check:")
#         print("  - Forward:  all 4 wheels spin same direction")
#         print("  - Strafe:   front/back pairs spin opposite directions")
#         print("  - Rotate:   left/right sides spin opposite directions")
#         print("  - Any wheel not spinning  → check ENA/ENB wiring")
#         print("  - Wrong direction         → swap IN1/IN2 for that motor")

#     except KeyboardInterrupt:
#         print("\n\n  *** INTERRUPTED ***")
#     finally:
#         print("\n  Stopping motors...")
#         motors.cleanup()
#         print("  Done.")


# if __name__ == '__main__':
#     main()
#!/usr/bin/env python3
"""
Motor Test Script - Mecanum Robot
Drives motors directly via gpiozero to L298N drivers.
Run directly on Pi 4, no ROS or Pico required.
"""

import time
from gpiozero import Motor
from gpiozero.pins.lgpio import LGPIOFactory

# ── Pin config ────────────────────────────────────────────────────────────────
# Left board
FL_ENA = 12   # PWM - FL speed
FL_IN1 =  7   # FL forward
FL_IN2 = 16   # FL backward
BL_ENB = 13   # PWM - BL speed
BL_IN3 =  6   # BL forward
BL_IN4 =  5   # BL backward

# Right board (forward/backward swapped — motors face opposite direction)
FR_ENA = 18   # PWM - FR speed
FR_IN1 = 14   # FR forward (swapped)
FR_IN2 = 15   # FR backward (swapped)
BR_ENB = 19   # PWM - BR speed
BR_IN3 = 21   # BR forward (swapped)
BR_IN4 = 20   # BR backward (swapped)

TEST_SPEED    = 0.3   # 0.0–1.0, safe for bench testing
TEST_DURATION = 3.0   # seconds per test


# ── Motor setup ───────────────────────────────────────────────────────────────
class Motors:
    def __init__(self):
        factory = LGPIOFactory()
        self.fl = Motor(forward=FL_IN1, backward=FL_IN2, enable=FL_ENA, pin_factory=factory)
        self.bl = Motor(forward=BL_IN3, backward=BL_IN4, enable=BL_ENB, pin_factory=factory)
        self.fr = Motor(forward=FR_IN1, backward=FR_IN2, enable=FR_ENA, pin_factory=factory)
        self.br = Motor(forward=BR_IN3, backward=BR_IN4, enable=BR_ENB, pin_factory=factory)
        print("✓ GPIO ready")

    def _set(self, motor, speed):
        """Set one motor. speed: -1.0 to 1.0"""
        speed = max(-1.0, min(1.0, speed))
        if speed > 0:
            motor.forward(speed)
        elif speed < 0:
            motor.backward(abs(speed))
        else:
            motor.stop()

    def set(self, fl, fr, bl, br):
        self._set(self.fl, fl)
        self._set(self.fr, fr)
        self._set(self.bl, bl)
        self._set(self.br, br)

    def mecanum(self, vx, vy, omega):
        """
        vx:    forward/backward  (+forward)
        vy:    strafe            (+right)
        omega: rotation          (+clockwise)
        All values -1.0 to 1.0
        """
        fl =  vx - vy - omega
        fr =  vx + vy + omega
        bl =  vx + vy - omega
        br =  vx - vy + omega

        mx = max(abs(fl), abs(fr), abs(bl), abs(br), 1.0)
        if mx > 1.0:
            fl, fr, bl, br = [v / mx for v in (fl, fr, bl, br)]

        self.set(fl, fr, bl, br)

    def stop(self):
        self.set(0, 0, 0, 0)

    def cleanup(self):
        self.stop()
        for m in [self.fl, self.fr, self.bl, self.br]:
            m.close()


# ── Test helpers ──────────────────────────────────────────────────────────────
def run(motors, label, vx=0.0, vy=0.0, omega=0.0, duration=TEST_DURATION):
    print(f"\n  → {label}")
    motors.mecanum(vx, vy, omega)
    time.sleep(duration)
    motors.stop()
    time.sleep(0.5)


def section(title):
    print(f"\n{'=' * 50}")
    print(f"  {title}")
    print('=' * 50)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    S = TEST_SPEED
    print("=" * 50)
    print("  MECANUM MOTOR TEST — GPIOZERO")
    print("=" * 50)
    print(f"\n  Speed:    {S * 100:.0f}%")
    print(f"  Duration: {TEST_DURATION}s per test")
    print("\n  Make sure wheels are off the ground!")
    input("\n  Press ENTER to start...\n")

    motors = Motors()

    try:
        section("TEST 1: Cardinal Directions")
        run(motors, "Forward",      vx= S)
        run(motors, "Backward",     vx=-S)
        run(motors, "Strafe right", vy= S)
        run(motors, "Strafe left",  vy=-S)

        section("TEST 2: Rotation")
        run(motors, "Rotate clockwise",         omega= S)
        run(motors, "Rotate counter-clockwise", omega=-S)

        section("TEST 3: Diagonal Movement")
        run(motors, "Diagonal forward-right", vx= S, vy= S)
        run(motors, "Diagonal forward-left",  vx= S, vy=-S)
        run(motors, "Diagonal back-right",    vx=-S, vy= S)
        run(motors, "Diagonal back-left",     vx=-S, vy=-S)

        section("TEST 4: Higher Speed (60%)")
        run(motors, "Forward at 60%",  vx= 0.6, duration=2.0)
        run(motors, "Backward at 60%", vx=-0.6, duration=2.0)

        print("\n" + "=" * 50)
        print("  ALL TESTS COMPLETE ✓")
        print("=" * 50)
        print("\n  What to check:")
        print("  - Forward:  all 4 wheels spin same direction")
        print("  - Strafe:   front/back pairs spin opposite directions")
        print("  - Rotate:   left/right sides spin opposite directions")
        print("  - Any wheel not spinning  → check ENA/ENB wiring")
        print("  - Wrong direction         → swap forward/backward pins for that motor")

    except KeyboardInterrupt:
        print("\n\n  *** INTERRUPTED ***")
    finally:
        print("\n  Stopping motors...")
        motors.cleanup()
        print("  Done.")


if __name__ == '__main__':
    main()
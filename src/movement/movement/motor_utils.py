"""
Motor control utilities using gpiozero for TB6612FNG motor drivers.
Manages 4 mecanum wheels with TB6612FNG dual motor driver boards.

TB6612FNG Configuration:
- Each TB6612FNG board controls 2 motors (Dual H-bridge)
- You'll need 2 TB6612FNG boards for 4 motors
- Each motor needs: IN1, IN2, PWM
- Each board has a STBY pin that must be HIGH to enable motors
"""

from gpiozero import Device, Motor, OutputDevice
from gpiozero.pins.lgpio import LGPIOFactory

# Set the GPIO factory to use lgpio
Device.pin_factory = LGPIOFactory()

# ====== PIN CONFIGURATION ======
# TB6612FNG Board 1 (Front wheels)
# TB6612FNG Board 2 (Back wheels)

MOTOR_PINS = {
    "front_left": {
        "in1": 17,
        "in2": 18,
        "pwm": 22,
        "board": 1
    },
    "front_right": {
        "in1": 23,
        "in2": 24,
        "pwm": 25,
        "board": 1
    },
    "back_left": {
        "in1": 5,
        "in2": 6,
        "pwm": 13,
        "board": 2
    },
    "back_right": {
        "in1": 19,
        "in2": 26,
        "pwm": 16,
        "board": 2
    }
}

# Standby pins for each TB6612FNG board
STBY_PINS = {
    1: 27,  # Board 1 standby pin
    2: 20   # Board 2 standby pin
}

# Global storage for motor and standby objects
motors = {}
stby_pins = {}


def setup():
    """
    Initialize motor objects and enable TB6612FNG standby pins.
    Must be called before using any motor control functions.
    """
    global motors, stby_pins

    # Initialize standby pins (must be HIGH to enable motors)
    for board_num, pin in STBY_PINS.items():
        stby_pins[board_num] = OutputDevice(pin)
        stby_pins[board_num].on()  # Enable the board
        print(f"Board {board_num} STBY pin {pin} enabled")

    # Initialize motor objects
    for motor_name, pins in MOTOR_PINS.items():
        motors[motor_name] = Motor(
            forward=pins["in1"],
            backward=pins["in2"],
            enable=pins["pwm"],
            pwm=True
        )
        print(f"  {motor_name}: IN1={pins['in1']}, IN2={pins['in2']}, PWM={pins['pwm']}")

    print(f"✓ {len(motors)} motors initialized successfully")


def stop_all():
    """
    Stop all motors immediately.
    """
    for motor_name, motor in motors.items():
        if motor:
            motor.stop()


def control_wheel(wheel_name, speed):
    """
    Control a specific wheel.

    Args:
        wheel_name (str): 'front_left', 'front_right', 'back_left', or 'back_right'
        speed (int): -100 to 100, where:
                    - positive values indicate forward movement
                    - negative values indicate backward movement
                    - 0 means stop
    """
    if wheel_name not in motors:
        raise ValueError(
            f"Invalid wheel name: {wheel_name}. Must be one of {list(motors.keys())}"
        )

    if not -100 <= speed <= 100:
        raise ValueError("Speed must be between -100 and 100")

    motor = motors[wheel_name]
    
    # Convert to -1.0 to 1.0 range for gpiozero
    normalized_speed = speed / 100.0

    if normalized_speed > 0:
        motor.forward(abs(normalized_speed))
    elif normalized_speed < 0:
        motor.backward(abs(normalized_speed))
    else:
        motor.stop()


def cleanup():
    """
    Clean up GPIO resources and disable motor drivers.
    Call this before exiting the program.
    """
    # Stop all motors
    stop_all()
    
    # Disable standby pins (puts drivers in low-power mode)
    for board_num, stby in stby_pins.items():
        if stby:
            stby.off()
            print(f"Board {board_num} STBY disabled")
    
    # Close motor objects
    for motor_name, motor in motors.items():
        if motor:
            motor.close()
    
    # Close standby pins
    for stby in stby_pins.values():
        if stby:
            stby.close()
    
    print("✓ TB6612FNG motor drivers cleaned up")


def test_wheel(wheel_name, duration=2):
    """
    Test a specific wheel by running it forward and backward.
    Useful for debugging motor connections.

    Args:
        wheel_name (str): 'front_left', 'front_right', 'back_left', or 'back_right'
        duration (int): Duration in seconds for each direction
    """
    import time
    
    if wheel_name not in motors:
        print(f"✗ Error: Unknown wheel '{wheel_name}'")
        return
    
    print(f"\n{'='*50}")
    print(f"Testing {wheel_name.upper().replace('_', ' ')}")
    print(f"{'='*50}")
    
    pins = MOTOR_PINS[wheel_name]
    print(f"Pins: IN1={pins['in1']}, IN2={pins['in2']}, PWM={pins['pwm']}, Board={pins['board']}")

    # Forward
    print(f"  → Forward at 50% for {duration} seconds...")
    control_wheel(wheel_name, 50)
    time.sleep(duration)

    # Stop
    print("  ⏸ Stopping for 1 second...")
    control_wheel(wheel_name, 0)
    time.sleep(1)

    # Backward
    print(f"  ← Backward at 50% for {duration} seconds...")
    control_wheel(wheel_name, -50)
    time.sleep(duration)

    # Stop
    print("  ⏹ Stopped")
    control_wheel(wheel_name, 0)


if __name__ == "__main__":
    """
    Test script - run this directly to test all motors.
    Usage: python3 motor_utils.py
    """
    import time
    
    print("\n" + "="*50)
    print("TB6612FNG MOTOR TEST SCRIPT")
    print("="*50 + "\n")
    
    try:
        setup()
        print("\n" + "="*50)
        print("Starting motor tests...")
        print("="*50)
        
        # Test each wheel in sequence
        for wheel_name in motors.keys():
            test_wheel(wheel_name, duration=2)
            time.sleep(1)
        
        print("\n" + "="*50)
        print("✓ ALL MOTORS TESTED SUCCESSFULLY!")
        print("="*50 + "\n")
        
    except KeyboardInterrupt:
        print("\n\n⚠ Test interrupted by user")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cleanup()
#!/usr/bin/env python3
"""
4-Motor Test with CONFIGURABLE motor mapping
Easily remap which pins control which physical motor location
"""

import RPi.GPIO as GPIO
import time

# ============================================================
# MOTOR CONFIGURATION - EDIT THIS SECTION TO FIX MAPPING
# ============================================================

# Physical motor locations mapped to GPIO pins
# Change the pin assignments to match your actual wiring
MOTOR_CONFIG = {
    'front_left': {
        'pwm': 12,
        'in1': 5,
        'in2': 6,
        'driver': 'front',
        'reverse': False  # Set True if this motor spins backwards
    },
    'front_right': {
        'pwm': 13,
        'in1': 7,
        'in2': 8,
        'driver': 'front',
        'reverse': False
    },
    'back_left': {
        'pwm': 18,
        'in1': 23,
        'in2': 24,
        'driver': 'back',
        'reverse': False
    },
    'back_right': {
        'pwm': 19,
        'in1': 16,
        'in2': 20,
        'driver': 'back',
        'reverse': False
    }
}

# Standby pins for each driver board
STANDBY_PINS = {
    'front': 25,
    'back': 26
}

# ============================================================
# END CONFIGURATION
# ============================================================


class ConfigurableMotorTester:
    def __init__(self):
        print("=" * 60)
        print("Configurable 4-Motor Tester")
        print("=" * 60)
        print("\nCurrent Motor Configuration:")
        for motor, config in MOTOR_CONFIG.items():
            reverse_str = " (REVERSED)" if config['reverse'] else ""
            print(f"  {motor:12s}: PWM={config['pwm']}, IN1={config['in1']}, IN2={config['in2']}{reverse_str}")
        print()
        
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # Setup standby pins
        for driver_name, pin in STANDBY_PINS.items():
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)
        
        # Setup motor pins
        self.pwm_objects = {}
        
        for motor_name, config in MOTOR_CONFIG.items():
            GPIO.setup(config['pwm'], GPIO.OUT)
            GPIO.setup(config['in1'], GPIO.OUT)
            GPIO.setup(config['in2'], GPIO.OUT)
            
            # Create PWM at 1000 Hz
            self.pwm_objects[motor_name] = GPIO.PWM(config['pwm'], 1000)
            self.pwm_objects[motor_name].start(0)
        
        print("✓ All motors initialized\n")
    
    def enable_driver(self, driver):
        """Enable a driver board"""
        GPIO.output(STANDBY_PINS[driver], GPIO.HIGH)
    
    def disable_driver(self, driver):
        """Disable a driver board"""
        GPIO.output(STANDBY_PINS[driver], GPIO.LOW)
    
    def test_motor(self, motor_name, speed, duration=2.0):
        """
        Test a single motor
        speed: -100 to 100 (positive = forward for that wheel position)
        """
        if motor_name not in MOTOR_CONFIG:
            print(f"Invalid motor: {motor_name}")
            return
        
        config = MOTOR_CONFIG[motor_name]
        pwm = self.pwm_objects[motor_name]
        
        # Apply reverse flag if set
        if config['reverse']:
            speed = -speed
        
        print(f"\n{'='*60}")
        print(f"Testing: {motor_name.upper().replace('_', ' ')}")
        print(f"{'='*60}")
        print(f"  Commanded speed: {speed}%")
        print(f"  Duration: {duration}s")
        print(f"  Reverse flag: {config['reverse']}")
        print()
        
        # Enable this motor's driver
        self.enable_driver(config['driver'])
        
        # Set direction
        if speed > 0:
            GPIO.output(config['in1'], GPIO.HIGH)
            GPIO.output(config['in2'], GPIO.LOW)
            print("  → Motor spinning FORWARD")
        elif speed < 0:
            GPIO.output(config['in1'], GPIO.LOW)
            GPIO.output(config['in2'], GPIO.HIGH)
            print("  → Motor spinning REVERSE")
        else:
            GPIO.output(config['in1'], GPIO.LOW)
            GPIO.output(config['in2'], GPIO.LOW)
            print("  → Motor STOPPED")
        
        # Set speed
        pwm.ChangeDutyCycle(abs(speed))
        
        print(f"\n  Watch the {motor_name.replace('_', ' ').upper()} wheel...")
        print("  (It should be the wheel in that physical position)")
        
        time.sleep(duration)
        
        # Stop
        pwm.ChangeDutyCycle(0)
        GPIO.output(config['in1'], GPIO.LOW)
        GPIO.output(config['in2'], GPIO.LOW)
        
        print(f"  ✓ Stopped\n")
    
    def stop_all(self):
        """Stop all motors"""
        for motor_name, config in MOTOR_CONFIG.items():
            self.pwm_objects[motor_name].ChangeDutyCycle(0)
            GPIO.output(config['in1'], GPIO.LOW)
            GPIO.output(config['in2'], GPIO.LOW)
        
        for driver in STANDBY_PINS.keys():
            self.disable_driver(driver)
    
    def cleanup(self):
        """Clean up GPIO"""
        print("\nCleaning up...")
        self.stop_all()
        for motor_name in list(self.pwm_objects.keys()):
            try:
                self.pwm_objects[motor_name].stop()
                del self.pwm_objects[motor_name]
            except:
                pass
        GPIO.cleanup()
        print("✓ Cleanup complete")


def interactive_test():
    """Interactive motor identification"""
    print("\n" + "=" * 60)
    print("INTERACTIVE MOTOR IDENTIFICATION MODE")
    print("=" * 60)
    print("\nThis will test each motor one at a time.")
    print("Watch which physical wheel spins and verify it matches the name.")
    print("\nRobot orientation:")
    print("       FRONT")
    print("   FL ---- FR")
    print("    |      |")
    print("   BL ---- BR")
    print("       BACK")
    print()
    
    tester = ConfigurableMotorTester()
    
    try:
        # Test each motor individually
        test_order = ['front_left', 'front_right', 'back_left', 'back_right']
        
        for motor in test_order:
            input(f"Press ENTER to test {motor.upper().replace('_', ' ')}...")
            tester.test_motor(motor, speed=40, duration=3)
            
            correct = input(f"  Did the correct wheel spin? (y/n): ").lower()
            direction = input(f"  Did it spin FORWARD (away from you)? (y/n): ").lower()
            
            if correct != 'y':
                print(f"  ⚠ MAPPING ISSUE: {motor} is wired to wrong position!")
            if direction != 'y':
                print(f"  ⚠ DIRECTION ISSUE: {motor} needs reverse flag!")
            print()
        
        print("\n" + "=" * 60)
        print("IDENTIFICATION COMPLETE")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted")
    finally:
        tester.cleanup()


def main():
    print("\n" + "=" * 60)
    print("MOTOR MAPPING TEST")
    print("=" * 60)
    print("\nWhat would you like to do?")
    print("  1) Interactive motor identification (recommended first time)")
    print("  2) Run full test sequence with current config")
    print("  3) Quick test - all motors forward")
    print()
    
    choice = input("Enter choice (1-3): ").strip()
    
    if choice == '1':
        interactive_test()
    
    elif choice == '2':
        tester = ConfigurableMotorTester()
        try:
            print("\n" + "=" * 60)
            print("FULL TEST SEQUENCE")
            print("=" * 60)
            
            print("\n### Individual Motor Tests ###")
            for motor in ['front_left', 'front_right', 'back_left', 'back_right']:
                tester.test_motor(motor, speed=40, duration=2)
                time.sleep(0.5)
            
            print("\n### All Motors Forward ###")
            input("Press ENTER to spin all motors forward...")
            for motor in MOTOR_CONFIG.keys():
                config = MOTOR_CONFIG[motor]
                tester.enable_driver(config['driver'])
                speed = 40 if not config['reverse'] else -40
                if speed > 0:
                    GPIO.output(config['in1'], GPIO.HIGH)
                    GPIO.output(config['in2'], GPIO.LOW)
                else:
                    GPIO.output(config['in1'], GPIO.LOW)
                    GPIO.output(config['in2'], GPIO.HIGH)
                tester.pwm_objects[motor].ChangeDutyCycle(abs(speed))
            
            print("All wheels spinning forward for 3 seconds...")
            time.sleep(3)
            tester.stop_all()
            
            print("\n✓ Test complete!")
            
        except KeyboardInterrupt:
            print("\n\nTest interrupted")
        finally:
            tester.cleanup()
    
    elif choice == '3':
        tester = ConfigurableMotorTester()
        try:
            print("\nSpinning all motors forward at 40% for 3 seconds...")
            for motor in MOTOR_CONFIG.keys():
                config = MOTOR_CONFIG[motor]
                tester.enable_driver(config['driver'])
                speed = 40 if not config['reverse'] else -40
                if speed > 0:
                    GPIO.output(config['in1'], GPIO.HIGH)
                    GPIO.output(config['in2'], GPIO.LOW)
                else:
                    GPIO.output(config['in1'], GPIO.LOW)
                    GPIO.output(config['in2'], GPIO.HIGH)
                tester.pwm_objects[motor].ChangeDutyCycle(abs(speed))
            time.sleep(3)
            tester.stop_all()
            print("✓ Done!")
        except KeyboardInterrupt:
            print("\n\nTest interrupted")
        finally:
            tester.cleanup()


if __name__ == '__main__':
    main()
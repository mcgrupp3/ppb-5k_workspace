#!/usr/bin/env python3
"""
4-Motor Test with Independent Standby Control
Tests all motors with ability to enable/disable front and back separately
"""

import RPi.GPIO as GPIO
import time

# Pin definitions
MOTOR_PINS = {
    'front_left': {
        'pwm': 18,      # Was back_left
        'in1': 23,
        'in2': 24,
        'driver': 'back',   # Now using back driver board
        'reverse': False
    },
    'front_right': {
        'pwm': 19,      # Was back_right
        'in1': 20,
        'in2': 16,
        'driver': 'back',   # Now using back driver board
        'reverse': False
    },
    'back_left': {
        'pwm': 12,      # Was front_left
        'in1': 5,
        'in2': 6,
        'driver': 'front',  # Now using front driver board
        'reverse': False
    },
    'back_right': {
        'pwm': 13,      # Was front_right
        'in1': 8,
        'in2': 7,
        'driver': 'front',  # Now using front driver board
        'reverse': False
    }
}

# Standby pins stay the same
STANDBY_PINS = {
    'front': 25,
    'back': 26
}


class FourMotorTester:
    def __init__(self):
        print("Initializing 4-motor test system with independent standby control...")
        
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # Setup standby pins
        for driver_name, pin in STANDBY_PINS.items():
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)  # Start disabled
            print(f"✓ {driver_name.upper()} driver standby pin configured (GPIO {pin})")
        
        # Setup motor pins
        self.pwm_objects = {}
        
        for motor_name, pins in MOTOR_PINS.items():
            GPIO.setup(pins['pwm'], GPIO.OUT)
            GPIO.setup(pins['in1'], GPIO.OUT)
            GPIO.setup(pins['in2'], GPIO.OUT)
            
            # Create PWM at 1000 Hz
            self.pwm_objects[motor_name] = GPIO.PWM(pins['pwm'], 1000)
            self.pwm_objects[motor_name].start(0)
            print(f"✓ {motor_name} initialized")
        
        print("\n4-Motor Tester Ready!\n")
    
    def enable_driver(self, driver):
        """Enable a driver board (front or back)"""
        GPIO.output(STANDBY_PINS[driver], GPIO.HIGH)
        print(f"→ {driver.upper()} driver ENABLED")
    
    def disable_driver(self, driver):
        """Disable a driver board (front or back)"""
        GPIO.output(STANDBY_PINS[driver], GPIO.LOW)
        print(f"→ {driver.upper()} driver DISABLED")
    
    def enable_all_drivers(self):
        """Enable both driver boards"""
        for driver in STANDBY_PINS.keys():
            self.enable_driver(driver)
    
    def disable_all_drivers(self):
        """Disable both driver boards"""
        for driver in STANDBY_PINS.keys():
            self.disable_driver(driver)
    
    def test_motor(self, motor_name, speed, duration=2.0):
        """
        Test a single motor
        motor_name: 'front_left', 'front_right', 'back_left', 'back_right'
        speed: -100 to 100
        duration: seconds
        """
        if motor_name not in MOTOR_PINS:
            print(f"Invalid motor: {motor_name}")
            return
        
        pins = MOTOR_PINS[motor_name]
        driver = pins['driver']
        pwm = self.pwm_objects[motor_name]
        
        print(f"\n{motor_name.upper().replace('_', ' ')}:")
        print(f"  Driver: {driver}")
        print(f"  Speed: {speed}%")
        print(f"  Duration: {duration}s")
        
        # Enable this motor's driver
        self.enable_driver(driver)
        
        # Set direction
        if speed > 0:
            GPIO.output(pins['in1'], GPIO.HIGH)
            GPIO.output(pins['in2'], GPIO.LOW)
            print("  Direction: FORWARD")
        elif speed < 0:
            GPIO.output(pins['in1'], GPIO.LOW)
            GPIO.output(pins['in2'], GPIO.HIGH)
            print("  Direction: REVERSE")
        else:
            GPIO.output(pins['in1'], GPIO.LOW)
            GPIO.output(pins['in2'], GPIO.LOW)
            print("  Direction: STOPPED")
        
        # Set speed
        pwm.ChangeDutyCycle(abs(speed))
        time.sleep(duration)
        
        # Stop
        pwm.ChangeDutyCycle(0)
        GPIO.output(pins['in1'], GPIO.LOW)
        GPIO.output(pins['in2'], GPIO.LOW)
        
        print(f"  ✓ Stopped")
    
    def test_driver_pair(self, driver, speed, duration=2.0):
        """Test both motors on one driver board"""
        print(f"\n*** Testing {driver.upper()} driver pair at {speed}% ***")
        
        # Enable this driver
        self.enable_driver(driver)
        
        # Find motors for this driver
        motors = [name for name, pins in MOTOR_PINS.items() if pins['driver'] == driver]
        
        for motor_name in motors:
            pins = MOTOR_PINS[motor_name]
            pwm = self.pwm_objects[motor_name]
            
            if speed > 0:
                GPIO.output(pins['in1'], GPIO.HIGH)
                GPIO.output(pins['in2'], GPIO.LOW)
            elif speed < 0:
                GPIO.output(pins['in1'], GPIO.LOW)
                GPIO.output(pins['in2'], GPIO.HIGH)
            else:
                GPIO.output(pins['in1'], GPIO.LOW)
                GPIO.output(pins['in2'], GPIO.LOW)
            
            pwm.ChangeDutyCycle(abs(speed))
        
        time.sleep(duration)
        
        # Stop these motors
        for motor_name in motors:
            pins = MOTOR_PINS[motor_name]
            self.pwm_objects[motor_name].ChangeDutyCycle(0)
            GPIO.output(pins['in1'], GPIO.LOW)
            GPIO.output(pins['in2'], GPIO.LOW)
        
        print(f"  ✓ {driver.upper()} motors stopped")
    
    def test_all_motors(self, speed, duration=2.0):
        """Run all 4 motors at same speed"""
        print(f"\n*** Running ALL 4 MOTORS at {speed}% for {duration}s ***")
        
        # Enable both drivers
        self.enable_all_drivers()
        
        for motor_name, pins in MOTOR_PINS.items():
            pwm = self.pwm_objects[motor_name]
            
            if speed > 0:
                GPIO.output(pins['in1'], GPIO.HIGH)
                GPIO.output(pins['in2'], GPIO.LOW)
            elif speed < 0:
                GPIO.output(pins['in1'], GPIO.LOW)
                GPIO.output(pins['in2'], GPIO.HIGH)
            else:
                GPIO.output(pins['in1'], GPIO.LOW)
                GPIO.output(pins['in2'], GPIO.LOW)
            
            pwm.ChangeDutyCycle(abs(speed))
        
        time.sleep(duration)
        self.stop_all()
    
    def stop_all(self):
        """Stop all motors and disable all drivers"""
        print("\n*** STOPPING ALL MOTORS ***")
        for motor_name, pins in MOTOR_PINS.items():
            self.pwm_objects[motor_name].ChangeDutyCycle(0)
            GPIO.output(pins['in1'], GPIO.LOW)
            GPIO.output(pins['in2'], GPIO.LOW)
        
        self.disable_all_drivers()
    
    def cleanup(self):
        """Clean up GPIO"""
        print("\nCleaning up GPIO...")
        self.stop_all()
        for pwm in self.pwm_objects.values():
            pwm.stop()
        GPIO.cleanup()
        print("✓ Cleanup complete")


def main():
    print("=" * 60)
    print("4-MOTOR TESTER - Independent Driver Control")
    print("=" * 60)
    print("\nHardware Setup:")
    print("  Driver 1 (Front): GPIO 25 STBY")
    print("    - Front Left:  GPIO 12, 5, 6")
    print("    - Front Right: GPIO 13, 7, 8")
    print("  Driver 2 (Back):  GPIO 26 STBY")
    print("    - Back Left:   GPIO 18, 23, 24")
    print("    - Back Right:  GPIO 19, 16, 20")
    print("\nSafety:")
    print("  1. Battery connected to BOTH driver VM pins")
    print("  2. All motors wired correctly")
    print("  3. Robot on blocks (wheels off ground!)")
    print("\nPress Ctrl+C to stop at any time\n")
    
    input("Press ENTER to start...")
    
    tester = FourMotorTester()
    
    try:
        print("\n" + "=" * 60)
        print("TEST SEQUENCE STARTING")
        print("=" * 60)
        
        # Test 1: Individual motors at low speed
        print("\n### TEST 1: Individual Motor Test - Low Speed Forward ###")
        for motor in ['front_left', 'front_right', 'back_left', 'back_right']:
            tester.test_motor(motor, speed=30, duration=2)
            tester.disable_all_drivers()  # Disable between tests
            time.sleep(1)
        
        # Test 2: Individual motors reverse
        print("\n### TEST 2: Individual Motor Test - Low Speed Reverse ###")
        for motor in ['front_left', 'front_right', 'back_left', 'back_right']:
            tester.test_motor(motor, speed=-30, duration=2)
            tester.disable_all_drivers()
            time.sleep(1)
        
        # Test 3: Front driver pair
        print("\n### TEST 3: Front Driver Pair Test ###")
        tester.test_driver_pair('front', speed=40, duration=3)
        tester.disable_all_drivers()
        time.sleep(1)
        
        # Test 4: Back driver pair
        print("\n### TEST 4: Back Driver Pair Test ###")
        tester.test_driver_pair('back', speed=40, duration=3)
        tester.disable_all_drivers()
        time.sleep(1)
        
        # Test 5: All motors forward
        print("\n### TEST 5: All Motors Forward ###")
        tester.test_all_motors(speed=40, duration=3)
        time.sleep(1)
        
        # Test 6: All motors reverse
        print("\n### TEST 6: All Motors Reverse ###")
        tester.test_all_motors(speed=-40, duration=3)
        time.sleep(1)
        
        # Test 7: Medium speed
        print("\n### TEST 7: All Motors - Medium Speed ###")
        tester.test_all_motors(speed=60, duration=2)
        
        print("\n" + "=" * 60)
        print("TEST COMPLETE - All 4 motors working! ✓")
        print("=" * 60)
        print("\nNext steps:")
        print("  - If all motors work, you can combine STBY pins later")
        print("  - Ready for ROS integration!")
        
    except KeyboardInterrupt:
        print("\n\n*** TEST INTERRUPTED ***")
    except Exception as e:
        print(f"\n*** ERROR: {e} ***")
    finally:
        tester.cleanup()


if __name__ == '__main__':
    main()
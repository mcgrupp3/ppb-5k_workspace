#!/usr/bin/env python3
"""
Motor Control Utilities for Mecanum Robot
Hardware interface for TB6612FNG motor drivers
"""

import os
os.environ['GPIOCHIP'] = '4'  # ← ADD THIS LINE


import RPi.GPIO as GPIO


class MotorController:
    """
    Controls 4 mecanum wheels via TB6612FNG drivers
    Provides velocity-based control interface
    """
    
    # Your validated motor configuration
    MOTOR_PINS = {
        'front_left': {'pwm': 18, 'in1': 23, 'in2': 24},
        'front_right': {'pwm': 19, 'in1': 16, 'in2': 20},
        'back_left': {'pwm': 12, 'in1': 6, 'in2': 5},
        'back_right': {'pwm': 13, 'in1': 7, 'in2': 8},
    }
    
    # Standby pins for each driver board
    STANDBY_PINS = {
        'front': 26,  # Controls front motors (Driver 2)
        'back': 25,   # Controls back motors (Driver 1)
    }
    
    def __init__(self, max_speed=100, pwm_freq=1000):
        """
        Initialize motor controller
        
        Args:
            max_speed: Maximum motor speed (0-100)
            pwm_freq: PWM frequency in Hz
        """
        self.max_speed = max_speed
        self.pwm_freq = pwm_freq
        
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # Setup standby pins
        for driver, pin in self.STANDBY_PINS.items():
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.HIGH)  # Enable drivers
        
        # Setup motor pins and create PWM objects
        self.pwm_objects = {}
        for motor, pins in self.MOTOR_PINS.items():
            GPIO.setup(pins['pwm'], GPIO.OUT)
            GPIO.setup(pins['in1'], GPIO.OUT)
            GPIO.setup(pins['in2'], GPIO.OUT)
            
            self.pwm_objects[motor] = GPIO.PWM(pins['pwm'], pwm_freq)
            self.pwm_objects[motor].start(0)
    
    def set_mecanum_velocity(self, vx, vy, omega):
        """
        Set velocity using mecanum wheel equations
        
        Args:
            vx: Forward/backward velocity (-1.0 to 1.0)
            vy: Left/right strafe velocity (-1.0 to 1.0)
            omega: Rotational velocity (-1.0 to 1.0)
        """
        # Mecanum wheel inverse kinematics
        # vx: positive = forward, negative = backward
        # vy: positive = right, negative = left
        # omega: positive = counter-clockwise, negative = clockwise
        
        fl = vx - vy - omega
        fr = vx + vy + omega
        bl = vx + vy - omega
        br = vx - vy + omega
        
        # Normalize if any wheel speed exceeds 1.0
        max_val = max(abs(fl), abs(fr), abs(bl), abs(br))
        if max_val > 1.0:
            fl /= max_val
            fr /= max_val
            bl /= max_val
            br /= max_val
        
        # Apply to motors
        self._set_motor('front_left', fl * self.max_speed)
        self._set_motor('front_right', fr * self.max_speed)
        self._set_motor('back_left', bl * self.max_speed)
        self._set_motor('back_right', br * self.max_speed)
    
    def _set_motor(self, motor_name, speed):
        """
        Set individual motor speed and direction
        
        Args:
            motor_name: 'front_left', 'front_right', 'back_left', 'back_right'
            speed: -100 to 100 (negative = reverse)
        """
        pins = self.MOTOR_PINS[motor_name]
        pwm = self.pwm_objects[motor_name]
        
        # Clamp speed
        speed = max(-self.max_speed, min(self.max_speed, speed))
        
        # Set direction
        if speed > 0:
            GPIO.output(pins['in1'], GPIO.HIGH)
            GPIO.output(pins['in2'], GPIO.LOW)
        elif speed < 0:
            GPIO.output(pins['in1'], GPIO.LOW)
            GPIO.output(pins['in2'], GPIO.HIGH)
        else:
            GPIO.output(pins['in1'], GPIO.LOW)
            GPIO.output(pins['in2'], GPIO.LOW)
        
        # Set speed
        pwm.ChangeDutyCycle(abs(speed))
    
    def stop(self):
        """Stop all motors"""
        for motor in self.MOTOR_PINS.keys():
            self._set_motor(motor, 0)
    
    def cleanup(self):
        """Clean up GPIO resources"""
        self.stop()
        for motor_name in list(self.pwm_objects.keys()):
            try:
                self.pwm_objects[motor_name].stop()
                del self.pwm_objects[motor_name]
            except:
                pass
        GPIO.cleanup()
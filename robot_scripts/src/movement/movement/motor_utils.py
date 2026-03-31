#!/usr/bin/env python3
"""
Motor Control Utilities for Mecanum Robot
Hardware interface for dual L298N motor drivers via gpiozero
Left board:  FL + BL
Right board: FR + BR
"""

from gpiozero import Motor
from gpiozero.pins.lgpio import LGPIOFactory


class MotorController:
    """
    Controls 4 mecanum wheels via dual L298N drivers
    Provides velocity-based control interface
    """

    def __init__(self, max_speed=1.0, pwm_freq=1000):
        """
        Initialize motor controller

        Args:
            max_speed: Maximum motor speed (0.0–1.0)
            pwm_freq:  PWM frequency in Hz (note: gpiozero default is 100Hz,
                       lgpio supports custom via pin factory if needed)
        """
        self.max_speed = max_speed
        factory = LGPIOFactory()

        # gpiozero Motor(forward_pin, backward_pin, enable=pwm_pin)
        self.motors = {
            'front_left':  Motor(forward=7,  backward=16, enable=12, pin_factory=factory),
            'back_left':   Motor(forward=6,  backward=5,  enable=13, pin_factory=factory),
            'front_right': Motor(forward=14, backward=15, enable=18, pin_factory=factory),  # inverted wrt FL
            'back_right':  Motor(forward=21, backward=20, enable=19, pin_factory=factory),  # inverted wrt BL
        }

    def set_mecanum_velocity(self, vx, vy, omega):
        """
        Set velocity using mecanum wheel equations

        Args:
            vx:    Forward/backward (-1.0 to 1.0)
            vy:    Left/right strafe (-1.0 to 1.0)
            omega: Rotational velocity (-1.0 to 1.0)
        """
        vx = -vx  # invert forward/backward to match physical motor orientation

        fl =  vx - vy - omega
        fr =  vx + vy + omega
        bl =  vx + vy - omega
        br =  vx - vy + omega

        # Normalize if any wheel exceeds 1.0
        max_val = max(abs(fl), abs(fr), abs(bl), abs(br), 1.0)
        if max_val > 1.0:
            fl /= max_val
            fr /= max_val
            bl /= max_val
            br /= max_val

        self._set_motor('front_left',  fl * self.max_speed)
        self._set_motor('front_right', fr * self.max_speed)
        self._set_motor('back_left',   bl * self.max_speed)
        self._set_motor('back_right',  br * self.max_speed)

    def _set_motor(self, name, speed):
        """
        Set individual motor speed and direction

        Args:
            name:  motor key
            speed: -1.0 to 1.0
        """
        m = self.motors[name]
        speed = max(-self.max_speed, min(self.max_speed, speed))

        if speed > 0:
            m.forward(speed)
        elif speed < 0:
            m.backward(abs(speed))
        else:
            m.stop()

    def stop(self):
        """Stop all motors"""
        for m in self.motors.values():
            m.stop()

    def cleanup(self):
        """Release GPIO resources"""
        self.stop()
        for m in self.motors.values():
            m.close()
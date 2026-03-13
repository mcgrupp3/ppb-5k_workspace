from machine import Pin, PWM
import time

def test_motor(pwm_pin, in1_pin, in2_pin, label):
    p = PWM(Pin(pwm_pin)); p.freq(1000); p.duty_u16(30000)
    in1 = Pin(in1_pin, Pin.OUT)
    in2 = Pin(in2_pin, Pin.OUT)
    
    print(f"{label} → forward")
    in1.on(); in2.off()
    time.sleep(2)
    
    print(f"{label} → reverse")
    in1.off(); in2.on()
    time.sleep(2)
    
    p.duty_u16(0); in1.off(); in2.off()
    print(f"{label} → done\n")
    time.sleep(1)

# Test each motor
test_motor(8,  7,  6,  "front_left")
test_motor(5,  4,  3,  "front_right")
test_motor(29, 28, 27, "back_left")
test_motor(26, 15, 14, "back_right")
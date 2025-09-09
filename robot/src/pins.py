"""GPIO pin definitions and PWM utilities for BevBot."""

from typing import Tuple

# Motor pin assignments
LEFT_MOTOR_R_EN = 5
LEFT_MOTOR_L_EN = 6
LEFT_MOTOR_RPWM = 18
LEFT_MOTOR_LPWM = 13

RIGHT_MOTOR_R_EN = 20
RIGHT_MOTOR_L_EN = 21
RIGHT_MOTOR_RPWM = 19
RIGHT_MOTOR_LPWM = 12

# Actuator pin assignments
ACTUATOR_R_EN = 16
ACTUATOR_L_EN = 26
ACTUATOR_RPWM = 23
ACTUATOR_LPWM = 24

# IO pins
BUTTON_PIN = 17
LED_BUZZER_PIN = 27

# PWM settings
PWM_FREQUENCY = 1000  # 1kHz
PWM_RANGE = 255       # 8-bit PWM resolution

def clamp_pwm_percent(percent: float) -> float:
    """Clamp PWM percentage to safe range 0-100%."""
    return max(0.0, min(100.0, percent))

def percent_to_pwm_value(percent: float) -> int:
    """Convert percentage (0-100) to PWM value (0-255)."""
    clamped = clamp_pwm_percent(percent)
    return int((clamped / 100.0) * PWM_RANGE)

def get_motor_pins(motor_type: str) -> Tuple[int, int, int, int]:
    """Get (R_EN, L_EN, RPWM, LPWM) pins for motor type."""
    if motor_type == "left":
        return (LEFT_MOTOR_R_EN, LEFT_MOTOR_L_EN, LEFT_MOTOR_RPWM, LEFT_MOTOR_LPWM)
    elif motor_type == "right":
        return (RIGHT_MOTOR_R_EN, RIGHT_MOTOR_L_EN, RIGHT_MOTOR_RPWM, RIGHT_MOTOR_LPWM)
    elif motor_type == "actuator":
        return (ACTUATOR_R_EN, ACTUATOR_L_EN, ACTUATOR_RPWM, ACTUATOR_LPWM)
    else:
        raise ValueError(f"Unknown motor type: {motor_type}")
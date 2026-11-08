"""Pure steering calculations for NightSentinel person tracking."""


def next_servo_angle(
    current_angle,
    target_center_x,
    frame_width,
    *,
    minimum_angle=30,
    maximum_angle=150,
    deadband_ratio=0.08,
    gain_degrees=24.0,
    maximum_step=6,
    direction=1,
):
    """Return a bounded servo angle, or the current angle inside deadband."""
    if frame_width <= 0:
        raise ValueError("frame_width must be positive")
    if direction not in (-1, 1):
        raise ValueError("direction must be -1 or 1")

    frame_center = frame_width / 2.0
    normalized_error = (target_center_x - frame_center) / frame_center
    if abs(normalized_error) <= deadband_ratio:
        return current_angle

    raw_step = round(normalized_error * gain_degrees * direction)
    if raw_step == 0:
        raw_step = direction if normalized_error > 0 else -direction

    bounded_step = max(-maximum_step, min(maximum_step, raw_step))
    requested_angle = current_angle + bounded_step
    return max(minimum_angle, min(maximum_angle, requested_angle))

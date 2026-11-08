"""Pure steering calculations for NightSentinel person tracking."""


def is_plausible_person_box(
    x1,
    y1,
    x2,
    y2,
    frame_width,
    frame_height,
    *,
    minimum_height_ratio=0.20,
    minimum_area_ratio=0.02,
):
    """Reject small class-0 false positives that cannot be a nearby person."""
    if frame_width <= 0 or frame_height <= 0:
        return False

    width = max(0.0, x2 - x1)
    height = max(0.0, y2 - y1)
    height_ratio = height / frame_height
    area_ratio = (width * height) / (frame_width * frame_height)
    return (
        height_ratio >= minimum_height_ratio
        and area_ratio >= minimum_area_ratio
    )


def select_target(
    visible_tracks,
    confirmed_track_ids,
    current_track_id=None,
):
    """Acquire the largest person, then keep that target until it is lost."""
    if current_track_id is not None:
        return current_track_id

    candidates = [
        track_id
        for track_id in confirmed_track_ids
        if track_id in visible_tracks
    ]
    if not candidates:
        return current_track_id

    largest_track_id = max(
        candidates,
        key=lambda track_id: visible_tracks[track_id]["area"],
    )
    return largest_track_id


def smooth_target_center(previous_center, observed_center, *, alpha=0.25):
    """Apply an exponential moving average to noisy detection centers."""
    if not 0 < alpha <= 1:
        raise ValueError("alpha must be greater than 0 and at most 1")
    if previous_center is None:
        return observed_center
    return previous_center + alpha * (observed_center - previous_center)


def next_servo_angle(
    current_angle,
    target_center_x,
    frame_width,
    *,
    minimum_angle=30,
    maximum_angle=150,
    deadband_ratio=0.12,
    gain_degrees=18.0,
    maximum_step=4,
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

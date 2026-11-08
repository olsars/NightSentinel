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
    *,
    switch_area_ratio=1.5,
):
    """Prefer the largest confirmed person while avoiding target jitter."""
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
    if current_track_id not in visible_tracks:
        return largest_track_id
    if largest_track_id == current_track_id:
        return current_track_id

    current_area = visible_tracks[current_track_id]["area"]
    largest_area = visible_tracks[largest_track_id]["area"]
    if largest_area >= current_area * switch_area_ratio:
        return largest_track_id
    return current_track_id


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

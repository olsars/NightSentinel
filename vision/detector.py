"""YOLO person detection, persistent tracking, and horizontal servo control."""

import os
import sys
import time
from pathlib import Path

from ultralytics import YOLO

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from hardware.serial_bridge import (  # noqa: E402
    ArduinoSerialBridge,
    SerialBridgeError,
)

try:  # Support both `python vision/detector.py` and module execution.
    from .events import send_event
    from .tracking import (
        is_plausible_person_box,
        next_servo_angle,
        select_target,
    )
    from .web_preview import WebPreviewServer
except ImportError:
    from events import send_event
    from tracking import is_plausible_person_box, next_servo_angle, select_target
    from web_preview import WebPreviewServer


SERIAL_PORT = os.getenv("NIGHTSENTINEL_SERIAL_PORT", "/dev/ttyUSB0")
SERIAL_BAUD = int(os.getenv("NIGHTSENTINEL_SERIAL_BAUD", "9600"))
SERVO_DIRECTION = int(os.getenv("NIGHTSENTINEL_SERVO_DIRECTION", "-1"))
STROBE_ENABLED = os.getenv("NIGHTSENTINEL_STROBE_ENABLED", "0") == "1"
SHOW_PREVIEW = os.getenv("NIGHTSENTINEL_SHOW_PREVIEW", "0") == "1"
CAMERA_SOURCE_VALUE = os.getenv("NIGHTSENTINEL_CAMERA_SOURCE", "0")
CAMERA_SOURCE = (
    int(CAMERA_SOURCE_VALUE)
    if CAMERA_SOURCE_VALUE.isdigit()
    else CAMERA_SOURCE_VALUE
)
MODEL_CONFIDENCE = float(os.getenv("NIGHTSENTINEL_CONFIDENCE", "0.4"))
STREAM_ENABLED = os.getenv("NIGHTSENTINEL_STREAM_ENABLED", "0") == "1"
STREAM_HOST = os.getenv("NIGHTSENTINEL_STREAM_HOST", "0.0.0.0")
STREAM_PORT = int(os.getenv("NIGHTSENTINEL_STREAM_PORT", "8080"))
STREAM_FPS = float(os.getenv("NIGHTSENTINEL_STREAM_FPS", "10"))

HOLD_CANDIDATE_FRAMES = 2
CONFIRMATION_FRAMES = 5
LOST_TARGET_FRAMES = 10
CANDIDATE_LOST_FRAMES = 6
SERVO_COMMAND_INTERVAL_SECONDS = float(
    os.getenv("NIGHTSENTINEL_SERVO_COMMAND_INTERVAL", "0.08")
)


def main():
    if SERVO_DIRECTION not in (-1, 1):
        raise ValueError("NIGHTSENTINEL_SERVO_DIRECTION must be 1 or -1")
    if SERVO_COMMAND_INTERVAL_SECONDS <= 0:
        raise ValueError(
            "NIGHTSENTINEL_SERVO_COMMAND_INTERVAL must be positive"
        )
    if not 1 <= STREAM_PORT <= 65535:
        raise ValueError("NIGHTSENTINEL_STREAM_PORT must be from 1 to 65535")
    if STREAM_FPS <= 0:
        raise ValueError("NIGHTSENTINEL_STREAM_FPS must be positive")

    model = YOLO("yolo11n.pt")
    alerted_tracks = set()
    strobe_tracks = set()
    confirmation_counts = {}

    target_track_id = None
    target_lost_frames = 0
    candidate_track_id = None
    candidate_lost_frames = 0
    current_servo_angle = 90
    servo_angle_known = False
    last_servo_command_time = 0.0
    last_stream_frame_time = 0.0
    proximity_near = False
    preview_server = None

    bridge = None
    try:
        bridge = ArduinoSerialBridge(SERIAL_PORT, SERIAL_BAUD, timeout=0)
        print(f"[SERIAL] Connected to {SERIAL_PORT}")
    except SerialBridgeError as error:
        print(f"[SERIAL] Unavailable; servo tracking disabled: {error}")

    def send_arduino_command(command):
        nonlocal bridge
        if bridge is None:
            return False
        try:
            bridge.send_command(command)
            print(f"[SERIAL] Sent: {command}")
            return True
        except (SerialBridgeError, ValueError) as error:
            print(f"[SERIAL] Command failed; disabling control: {error}")
            bridge.close()
            bridge = None
            return False

    print("[NightSentinel] Starting vision system...")
    print(f"[NightSentinel] Camera source: {CAMERA_SOURCE}")
    print(
        "[NightSentinel] Strobe authorization is "
        f"{'ENABLED' if STROBE_ENABLED else 'DISABLED'}"
    )
    if STREAM_ENABLED:
        try:
            preview_server = WebPreviewServer(STREAM_HOST, STREAM_PORT)
            preview_server.start()
            print(
                "[NightSentinel] Laptop preview: "
                f"http://<jetson-ip>:{STREAM_PORT}"
            )
        except OSError as error:
            print(f"[PREVIEW] Unable to start web preview: {error}")

    results = model.track(
        source=CAMERA_SOURCE,
        device=0,
        classes=[0],
        conf=MODEL_CONFIDENCE,
        tracker="bytetrack.yaml",
        persist=True,
        stream=True,
        show=SHOW_PREVIEW,
        verbose=False,
    )

    try:
        for result in results:
            if preview_server is not None:
                now = time.monotonic()
                if now - last_stream_frame_time >= 1.0 / STREAM_FPS:
                    preview_server.publish_image(result.plot())
                    last_stream_frame_time = now

            if bridge is not None:
                try:
                    for reading in bridge.poll():
                        if reading.get("sensor") == "servo":
                            current_servo_angle = reading["angle"]
                            servo_angle_known = True
                            continue
                        if reading.get("sensor") != "ultrasonic":
                            continue
                        if reading.get("event_type") == "proximity_near":
                            proximity_near = True
                        elif reading.get("event_type") == "proximity_cleared":
                            proximity_near = False
                except SerialBridgeError as error:
                    print(f"[SERIAL] Disconnected: {error}")
                    bridge.close()
                    bridge = None

            visible_tracks = {}
            frame_height = int(result.orig_shape[0])
            frame_width = int(result.orig_shape[1])
            if result.boxes is not None:
                for box in result.boxes:
                    if box.id is None:
                        continue

                    track_id = int(box.id.item())
                    confidence = float(box.conf.item())
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    if not is_plausible_person_box(
                        x1,
                        y1,
                        x2,
                        y2,
                        frame_width,
                        frame_height,
                    ):
                        continue

                    visible_tracks[track_id] = {
                        "confidence": confidence,
                        "center_x": (x1 + x2) / 2.0,
                        "area": (x2 - x1) * (y2 - y1),
                    }

            for track_id in list(confirmation_counts):
                if track_id not in visible_tracks:
                    confirmation_counts[track_id] = 0

            # Stop a moving sweep early so YOLO can confirm the candidate on
            # stable frames. Small false positives have already been filtered.
            if target_track_id is None:
                if candidate_track_id in visible_tracks:
                    candidate_lost_frames = 0
                elif candidate_track_id is not None:
                    candidate_lost_frames += 1
                    if candidate_lost_frames >= CANDIDATE_LOST_FRAMES:
                        print(
                            f"[TRACKING] Candidate {candidate_track_id} lost; "
                            "resuming scan"
                        )
                        candidate_track_id = None
                        candidate_lost_frames = 0
                        servo_angle_known = False
                        send_arduino_command("SERVO_SCAN")

                if candidate_track_id is None:
                    hold_candidates = [
                        track_id
                        for track_id in visible_tracks
                        if confirmation_counts.get(track_id, 0)
                        >= HOLD_CANDIDATE_FRAMES
                    ]
                    if hold_candidates:
                        candidate_track_id = max(
                            hold_candidates,
                            key=lambda track_id: visible_tracks[track_id]["area"],
                        )
                        candidate_lost_frames = 0
                        servo_angle_known = False
                        send_arduino_command("SERVO_STOP")
                        print(
                            f"[TRACKING] Holding sweep for candidate "
                            f"{candidate_track_id}"
                        )

            for track_id, detection in visible_tracks.items():
                confirmation_counts[track_id] = (
                    confirmation_counts.get(track_id, 0) + 1
                )
                if confirmation_counts[track_id] < CONFIRMATION_FRAMES:
                    continue

                print(
                    f"[DETECTION] Confirmed person | Track ID: {track_id} | "
                    f"Confidence: {detection['confidence']:.2f}"
                )

                if track_id not in alerted_tracks:
                    success = send_event(
                        track_id=track_id,
                        event_type="person_detected",
                        zone="front_door",
                    )
                    if success:
                        alerted_tracks.add(track_id)

            confirmed_tracks = [
                track_id
                for track_id in visible_tracks
                if confirmation_counts.get(track_id, 0) >= CONFIRMATION_FRAMES
            ]

            selected_track_id = select_target(
                visible_tracks,
                confirmed_tracks,
                target_track_id,
            )
            if selected_track_id != target_track_id:
                previous_track_id = target_track_id
                target_track_id = selected_track_id
                candidate_track_id = None
                candidate_lost_frames = 0
                target_lost_frames = 0
                servo_angle_known = False
                send_arduino_command("SERVO_STOP")
                if previous_track_id is None:
                    print(f"[TRACKING] Locked track {target_track_id}")
                else:
                    print(
                        f"[TRACKING] Switched from track {previous_track_id} "
                        f"to larger track {target_track_id}"
                    )

            if target_track_id not in visible_tracks:
                if target_track_id is not None:
                    target_lost_frames += 1
                    if target_lost_frames >= LOST_TARGET_FRAMES:
                        print(f"[TRACKING] Lost track {target_track_id}")
                        target_track_id = None
                        target_lost_frames = 0
                        servo_angle_known = False
                        send_arduino_command("SERVO_SCAN")
                continue

            target_lost_frames = 0
            if not servo_angle_known:
                continue

            target_center_x = visible_tracks[target_track_id]["center_x"]
            requested_angle = next_servo_angle(
                current_servo_angle,
                target_center_x,
                frame_width,
                direction=SERVO_DIRECTION,
            )

            now = time.monotonic()
            if (
                requested_angle != current_servo_angle
                and now - last_servo_command_time
                >= SERVO_COMMAND_INTERVAL_SECONDS
            ):
                if send_arduino_command(f"SERVO_ANGLE:{requested_angle}"):
                    current_servo_angle = requested_angle
                    last_servo_command_time = now

            # Disabled by default. Enabling this still requires both confirmed
            # YOLO tracking and a confirmed ultrasonic near state.
            if (
                STROBE_ENABLED
                and proximity_near
                and target_track_id not in strobe_tracks
            ):
                if send_arduino_command("TRIGGER_STROBE"):
                    strobe_tracks.add(target_track_id)

    except KeyboardInterrupt:
        print("\n[NightSentinel] Stopping vision system...")

    except ConnectionError as error:
        print(f"[CAMERA] Unable to start source {CAMERA_SOURCE}: {error}")

    finally:
        if preview_server is not None:
            preview_server.stop()

        if bridge is not None:
            try:
                bridge.send_command("RESET_SYSTEM")
            except SerialBridgeError:
                pass
            bridge.close()

        if hasattr(results, "close"):
            results.close()

        print("[NightSentinel] Vision system stopped.")


if __name__ == "__main__":
    main()

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
    from .tracking import next_servo_angle
except ImportError:
    from events import send_event
    from tracking import next_servo_angle


SERIAL_PORT = os.getenv("NIGHTSENTINEL_SERIAL_PORT", "/dev/ttyUSB0")
SERIAL_BAUD = int(os.getenv("NIGHTSENTINEL_SERIAL_BAUD", "9600"))
SERVO_DIRECTION = int(os.getenv("NIGHTSENTINEL_SERVO_DIRECTION", "1"))
STROBE_ENABLED = os.getenv("NIGHTSENTINEL_STROBE_ENABLED", "0") == "1"
SHOW_PREVIEW = os.getenv("NIGHTSENTINEL_SHOW_PREVIEW", "0") == "1"

CONFIRMATION_FRAMES = 3
LOST_TARGET_FRAMES = 10
SERVO_COMMAND_INTERVAL_SECONDS = 0.10


def main():
    if SERVO_DIRECTION not in (-1, 1):
        raise ValueError("NIGHTSENTINEL_SERVO_DIRECTION must be 1 or -1")

    model = YOLO("yolo11n.pt")
    alerted_tracks = set()
    strobe_tracks = set()
    confirmation_counts = {}

    target_track_id = None
    target_lost_frames = 0
    current_servo_angle = 90
    servo_angle_known = False
    last_servo_command_time = 0.0
    proximity_near = False

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
    print(
        "[NightSentinel] Strobe authorization is "
        f"{'ENABLED' if STROBE_ENABLED else 'DISABLED'}"
    )

    results = model.track(
        source=0,
        device=0,
        classes=[0],
        conf=0.5,
        tracker="bytetrack.yaml",
        persist=True,
        stream=True,
        show=SHOW_PREVIEW,
        verbose=False,
    )

    try:
        for result in results:
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
            if result.boxes is not None:
                for box in result.boxes:
                    if box.id is None:
                        continue

                    track_id = int(box.id.item())
                    confidence = float(box.conf.item())
                    x1, _y1, x2, _y2 = box.xyxy[0].tolist()
                    visible_tracks[track_id] = {
                        "confidence": confidence,
                        "center_x": (x1 + x2) / 2.0,
                    }

            for track_id in list(confirmation_counts):
                if track_id not in visible_tracks:
                    confirmation_counts[track_id] = 0

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

            if target_track_id is None and confirmed_tracks:
                target_track_id = max(
                    confirmed_tracks,
                    key=lambda track_id: visible_tracks[track_id]["confidence"],
                )
                target_lost_frames = 0
                servo_angle_known = False
                send_arduino_command("SERVO_STOP")
                print(f"[TRACKING] Locked track {target_track_id}")

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

            frame_width = int(result.orig_shape[1])
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

    finally:
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


import argparse
import json
import re
import sys
from datetime import datetime, timezone

LIGHT_PATTERN = re.compile(
    r"\[(DAYTIME|NIGHTTIME) MODE\] LDR Light Level: (\d+)",
    re.IGNORECASE
)
DISTANCE_PATTERN = re.compile(
    r"^DISTANCE_CM:([+-]?(?:\d+(?:\.\d*)?|\.\d+))$",
    re.IGNORECASE,
)

EVENTS = {
    "EVENT:RADAR_TRIPPED": ("mmwave", "radar_tripped"),
    "EVENT:PROXIMITY_NEAR": ("ultrasonic", "proximity_near"),
    "EVENT:PROXIMITY_CLEARED": ("ultrasonic", "proximity_cleared"),
}


def utc_timestamp():
    return datetime.now(timezone.utc).isoformat()


def parse_message(message):
    if not isinstance(message, str):
        return None

    normalized = message.strip()
    if not normalized:
        return None

    event = EVENTS.get(normalized.upper())
    if event:
        sensor, event_type = event
        return {
            "sensor": sensor,
            "event_type": event_type,
            "timestamp": utc_timestamp(),
        }

    if normalized.upper() == "DISTANCE_CM:INVALID":
        return {
            "sensor": "ultrasonic",
            "distance_cm": None,
            "valid": False,
            "timestamp": utc_timestamp(),
        }

    match = DISTANCE_PATTERN.fullmatch(normalized)
    if match:
        try:
            distance_cm = float(match.group(1))
        except ValueError:
            return None

        if distance_cm < 0:
            return None

        return {
            "sensor": "ultrasonic",
            "distance_cm": distance_cm,
            "timestamp": utc_timestamp(),
        }

    match = LIGHT_PATTERN.search(normalized)

    if match:
        return {
            "sensor": "ldr",
            "mode": match.group(1).lower(),
            "light_level": int(match.group(2)),
            "timestamp": utc_timestamp(),
        }

    return None


def process_message(message):
    reading = parse_message(message)

    if reading:
        print(json.dumps(reading))
    elif isinstance(message, str) and message.strip():
        print(f"[UNRECOGNIZED] {message.strip()}")

    return reading


def run_serial(port, baud):
    try:
        import serial
    except ImportError:
        print(
            "[SERIAL ERROR] pyserial is not installed; use --simulate or "
            "install pyserial.",
            file=sys.stderr,
        )
        return 1

    try:
        # This bridge must be the only process opening the Arduino serial port.
        with serial.Serial(port, baud, timeout=2) as connection:
            print(f"[CONNECTED] {port}")

            while True:
                raw_message = connection.readline()
                message = raw_message.decode(
                    "utf-8", errors="replace"
                ).strip()

                if message:
                    process_message(message)
    except (serial.SerialException, OSError) as error:
        print(f"[SERIAL ERROR] {port}: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n[DISCONNECTED] Serial bridge stopped.")
        return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--port", default="/dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=9600)
    args = parser.parse_args()

    if args.simulate:
        messages = [
            "[DAYTIME MODE] LDR Light Level: 541 (Resting to save power)",
            "[NIGHTTIME MODE] LDR Light Level: 84",
            "EVENT:RADAR_TRIPPED",
            "DISTANCE_CM:185.4",
            "DISTANCE_CM:98.5",
            "DISTANCE_CM:91.2",
            "DISTANCE_CM:85.6",
            "EVENT:PROXIMITY_NEAR",
            "DISTANCE_CM:INVALID",
            "DISTANCE_CM:145.1",
            "EVENT:PROXIMITY_CLEARED",
        ]

        for message in messages:
            process_message(message)
        return 0

    return run_serial(args.port, args.baud)


if __name__ == "__main__":
    raise SystemExit(main())


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
LEGACY_JSN_DISTANCE_PATTERN = re.compile(
    r"\[JSN VERIFIED\]\s+Confirmed target at\s+"
    r"(\d+(?:\.\d+)?)\s*cm\.?",
    re.IGNORECASE,
)
SERVO_ANGLE_PATTERN = re.compile(r"^STATE:SERVO_ANGLE:(\d+)$")
JETSON_ONLINE_PATTERN = re.compile(r"^STATE:JETSON_ONLINE:([01])$")

EVENTS = {
    "EVENT:RADAR_TRIPPED": ("mmwave", "radar_tripped"),
    "EVENT:PROXIMITY_NEAR": ("ultrasonic", "proximity_near"),
    "EVENT:PROXIMITY_CLEARED": ("ultrasonic", "proximity_cleared"),
    "EVENT:STROBE_STARTED": ("deterrent", "strobe_started"),
    "EVENT:STROBE_COMPLETE": ("deterrent", "strobe_complete"),
    "EVENT:STROBE_ABORTED": ("deterrent", "strobe_aborted"),
    # Compatibility with the firmware that preceded the standardized protocol.
    "EVENT:JSN_TRIGGERED": ("ultrasonic", "proximity_near"),
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

    legacy_match = LEGACY_JSN_DISTANCE_PATTERN.search(normalized)
    if legacy_match:
        return {
            "sensor": "ultrasonic",
            "distance_cm": float(legacy_match.group(1)),
            "timestamp": utc_timestamp(),
        }

    servo_match = SERVO_ANGLE_PATTERN.fullmatch(normalized)
    if servo_match:
        return {
            "sensor": "servo",
            "angle": int(servo_match.group(1)),
            "timestamp": utc_timestamp(),
        }

    jetson_match = JETSON_ONLINE_PATTERN.fullmatch(normalized)
    if jetson_match:
        return {
            "sensor": "control",
            "jetson_online": jetson_match.group(1) == "1",
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


class SerialBridgeError(Exception):
    """Raised when the single Arduino serial connection fails."""


class ArduinoSerialBridge:
    """Own the bidirectional Arduino connection for one process."""

    def __init__(self, port="/dev/ttyUSB0", baud=9600, timeout=0):
        try:
            import serial
        except ImportError as error:
            raise SerialBridgeError("pyserial is not installed") from error

        self._serial = serial
        try:
            self._connection = serial.Serial(port, baud, timeout=timeout)
        except (serial.SerialException, OSError) as error:
            raise SerialBridgeError(f"{port}: {error}") from error

        self.port = port
        self._receive_buffer = bytearray()

    @property
    def in_waiting(self):
        try:
            return self._connection.in_waiting
        except (self._serial.SerialException, OSError) as error:
            raise SerialBridgeError(f"{self.port}: {error}") from error

    def read_message(self):
        try:
            raw_message = self._connection.readline()
        except (self._serial.SerialException, OSError) as error:
            raise SerialBridgeError(f"{self.port}: {error}") from error

        return raw_message.decode("utf-8", errors="replace").strip()

    def poll(self):
        """Parse all complete messages currently buffered by the Arduino."""
        readings = []
        available = self.in_waiting
        if available > 0:
            try:
                self._receive_buffer.extend(self._connection.read(available))
            except (self._serial.SerialException, OSError) as error:
                raise SerialBridgeError(f"{self.port}: {error}") from error

        while b"\n" in self._receive_buffer:
            raw_message, _, remaining = self._receive_buffer.partition(b"\n")
            self._receive_buffer = bytearray(remaining)
            message = raw_message.decode("utf-8", errors="replace").strip()
            if not message:
                continue
            reading = process_message(message)
            if reading:
                readings.append(reading)
        return readings

    def send_command(self, command):
        normalized = command.strip()
        if not normalized or "\n" in normalized or "\r" in normalized:
            raise ValueError("serial command must be one non-empty line")

        try:
            self._connection.write(f"{normalized}\n".encode("ascii"))
            self._connection.flush()
        except (self._serial.SerialException, OSError) as error:
            raise SerialBridgeError(f"{self.port}: {error}") from error

    def close(self):
        if self._connection.is_open:
            self._connection.close()

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        self.close()


def run_serial(port, baud):
    try:
        # This bridge must be the only process opening the Arduino serial port.
        with ArduinoSerialBridge(port, baud, timeout=2) as bridge:
            print(f"[CONNECTED] {port}")

            while True:
                message = bridge.read_message()
                if message:
                    process_message(message)
    except SerialBridgeError as error:
        print(f"[SERIAL ERROR] {error}", file=sys.stderr)
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

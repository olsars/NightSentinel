
import argparse
import json
import re
from datetime import datetime, timezone

LIGHT_PATTERN = re.compile(
    r"\[(DAYTIME|NIGHTTIME) MODE\] LDR Light Level: (\d+)",
    re.IGNORECASE
)


def parse_message(message):
    match = LIGHT_PATTERN.search(message)

    if match:
        return {
            "sensor": "ldr",
            "mode": match.group(1).lower(),
            "light_level": int(match.group(2)),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    return None


def process_message(message):
    reading = parse_message(message)

    if reading:
        print(json.dumps(reading))
    else:
        print(f"[UNRECOGNIZED] {message.strip()}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--port", default="/dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=9600)
    args = parser.parse_args()

    if args.simulate:
        messages = [
            "[DAYTIME MODE] LDR Light Level: 541 (Resting to save power)",
            "[DAYTIME MODE] LDR Light Level: 102 (Resting to save power)",
            "[DAYTIME MODE] LDR Light Level: 84 (Resting to save power)"
        ]

        for message in messages:
            process_message(message)
        return

    import serial

    with serial.Serial(args.port, args.baud, timeout=2) as connection:
        print(f"[CONNECTED] {args.port}")

        while True:
            message = connection.readline().decode(
                "utf-8", errors="replace"
            ).strip()

            if message:
                process_message(message)


if __name__ == "__main__":
    main()

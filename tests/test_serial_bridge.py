import unittest
from datetime import datetime

from hardware.serial_bridge import parse_message


class SerialBridgeParserTests(unittest.TestCase):
    def assert_utc_timestamp(self, reading):
        parsed = datetime.fromisoformat(reading["timestamp"])
        self.assertIsNotNone(parsed.tzinfo)

    def test_valid_ultrasonic_distance(self):
        reading = parse_message("DISTANCE_CM:125.5")

        self.assertEqual(reading["sensor"], "ultrasonic")
        self.assertEqual(reading["distance_cm"], 125.5)
        self.assert_utc_timestamp(reading)

    def test_invalid_ultrasonic_distance(self):
        reading = parse_message("DISTANCE_CM:INVALID")

        self.assertEqual(reading["sensor"], "ultrasonic")
        self.assertIsNone(reading["distance_cm"])
        self.assertFalse(reading["valid"])
        self.assert_utc_timestamp(reading)

    def test_radar_event(self):
        reading = parse_message("EVENT:RADAR_TRIPPED")

        self.assertEqual(reading["sensor"], "mmwave")
        self.assertEqual(reading["event_type"], "radar_tripped")
        self.assert_utc_timestamp(reading)

    def test_proximity_near_event(self):
        reading = parse_message("EVENT:PROXIMITY_NEAR")

        self.assertEqual(reading["sensor"], "ultrasonic")
        self.assertEqual(reading["event_type"], "proximity_near")

    def test_proximity_cleared_event(self):
        reading = parse_message("EVENT:PROXIMITY_CLEARED")

        self.assertEqual(reading["sensor"], "ultrasonic")
        self.assertEqual(reading["event_type"], "proximity_cleared")

    def test_daytime_ldr_message(self):
        reading = parse_message(
            "[DAYTIME MODE] LDR Light Level: 357 (Resting to save power)"
        )

        self.assertEqual(reading["sensor"], "ldr")
        self.assertEqual(reading["mode"], "daytime")
        self.assertEqual(reading["light_level"], 357)

    def test_nighttime_ldr_message(self):
        reading = parse_message(
            "[NIGHTTIME MODE] LDR Light Level: 0"
        )

        self.assertEqual(reading["sensor"], "ldr")
        self.assertEqual(reading["mode"], "nighttime")
        self.assertEqual(reading["light_level"], 0)

    def test_empty_and_malformed_input(self):
        malformed_messages = (
            "",
            "   ",
            "DISTANCE_CM:not-a-number",
            "DISTANCE_CM:-3.2",
            "EVENT:UNKNOWN",
            None,
        )

        for message in malformed_messages:
            with self.subTest(message=message):
                self.assertIsNone(parse_message(message))


if __name__ == "__main__":
    unittest.main()

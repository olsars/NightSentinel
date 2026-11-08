import unittest

from vision.tracking import next_servo_angle


class ServoTrackingTests(unittest.TestCase):
    def test_centered_target_holds_angle(self):
        self.assertEqual(next_servo_angle(90, 640, 1280), 90)

    def test_target_right_increases_angle(self):
        self.assertGreater(next_servo_angle(90, 1000, 1280), 90)

    def test_target_left_decreases_angle(self):
        self.assertLess(next_servo_angle(90, 200, 1280), 90)

    def test_direction_can_be_reversed(self):
        self.assertLess(
            next_servo_angle(90, 1000, 1280, direction=-1),
            90,
        )

    def test_angle_is_clamped_to_safe_range(self):
        self.assertEqual(next_servo_angle(149, 1280, 1280), 150)
        self.assertEqual(next_servo_angle(31, 0, 1280), 30)

    def test_invalid_frame_width_is_rejected(self):
        with self.assertRaises(ValueError):
            next_servo_angle(90, 0, 0)


if __name__ == "__main__":
    unittest.main()

import unittest

from vision.tracking import (
    is_plausible_person_box,
    next_servo_angle,
    select_target,
)


class ServoTrackingTests(unittest.TestCase):
    def test_small_hand_sized_box_is_rejected(self):
        self.assertFalse(
            is_plausible_person_box(10, 10, 80, 80, 640, 480)
        )

    def test_nearby_person_box_is_accepted(self):
        self.assertTrue(
            is_plausible_person_box(160, 70, 480, 470, 640, 480)
        )

    def test_largest_confirmed_person_is_selected(self):
        tracks = {
            1: {"area": 10_000},
            2: {"area": 80_000},
        }
        self.assertEqual(select_target(tracks, [1, 2]), 2)

    def test_current_target_is_kept_without_large_challenger(self):
        tracks = {
            1: {"area": 60_000},
            2: {"area": 70_000},
        }
        self.assertEqual(select_target(tracks, [1, 2], 1), 1)

    def test_substantially_larger_person_replaces_target(self):
        tracks = {
            1: {"area": 40_000},
            2: {"area": 80_000},
        }
        self.assertEqual(select_target(tracks, [1, 2], 1), 2)

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

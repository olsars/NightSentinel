import unittest

from vision.tracking import (
    is_plausible_person_box,
    next_servo_angle,
    select_target,
    smooth_target_center,
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

    def test_moderately_sized_person_box_is_accepted(self):
        self.assertTrue(
            is_plausible_person_box(220, 150, 420, 390, 640, 480)
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

    def test_current_target_is_sticky_when_larger_person_appears(self):
        tracks = {
            1: {"area": 40_000},
            2: {"area": 80_000},
        }
        self.assertEqual(select_target(tracks, [1, 2], 1), 1)

    def test_current_target_is_retained_during_short_detection_gap(self):
        self.assertEqual(select_target({}, [], 7), 7)

    def test_first_center_observation_is_not_delayed(self):
        self.assertEqual(smooth_target_center(None, 400), 400)

    def test_center_observations_are_smoothed(self):
        self.assertEqual(smooth_target_center(400, 600), 450)

    def test_invalid_smoothing_alpha_is_rejected(self):
        with self.assertRaises(ValueError):
            smooth_target_center(400, 600, alpha=0)

    def test_centered_target_holds_angle(self):
        self.assertEqual(next_servo_angle(90, 640, 1280), 90)

    def test_small_center_jitter_holds_angle(self):
        self.assertEqual(next_servo_angle(90, 700, 1280), 90)

    def test_large_error_is_limited_to_four_degree_step(self):
        self.assertEqual(next_servo_angle(90, 1280, 1280), 94)

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

import unittest

from vision.web_preview import PreviewFrameStore


class PreviewFrameStoreTests(unittest.TestCase):
    def test_published_frame_is_returned(self):
        store = PreviewFrameStore()
        store.publish(b"jpeg-data")

        sequence, frame = store.wait_for_frame(0, timeout=0)

        self.assertEqual(sequence, 1)
        self.assertEqual(frame, b"jpeg-data")

    def test_no_new_frame_returns_none(self):
        store = PreviewFrameStore()
        store.publish(b"jpeg-data")

        sequence, frame = store.wait_for_frame(1, timeout=0)

        self.assertEqual(sequence, 1)
        self.assertIsNone(frame)


if __name__ == "__main__":
    unittest.main()

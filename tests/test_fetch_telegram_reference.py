import unittest

from scripts.fetch_telegram_reference import fetch_reference


class TelegramReferenceFetchTests(unittest.TestCase):
    def test_rejects_invalid_file_id_before_network_access(self):
        with self.assertRaisesRegex(ValueError, "file_id"):
            fetch_reference("../secret", "image", "image/jpeg", "out", "token")

    def test_rejects_unsupported_mime_before_network_access(self):
        with self.assertRaisesRegex(ValueError, "Only JPG"):
            fetch_reference("A" * 20, "video", "application/zip", "out", "token")

    def test_rejects_unknown_reference_kind(self):
        with self.assertRaisesRegex(ValueError, "Only JPG"):
            fetch_reference("A" * 20, "document", "image/jpeg", "out", "token")


if __name__ == "__main__":
    unittest.main()

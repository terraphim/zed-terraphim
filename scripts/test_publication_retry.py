"""Regression for a second readback retaining the first attempt's evidence."""
from pathlib import Path
import tempfile
import unittest
from publish_github import fresh_readback


class RetryTest(unittest.TestCase):
    def test_retry_retains_previous_download_and_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            first = fresh_readback(Path(folder))
            (first / "receipt.json").write_text('partial previous attempt')
            second = fresh_readback(Path(folder))
            self.assertNotEqual(first, second)
            self.assertEqual((first / "receipt.json").read_text(), 'partial previous attempt')
            self.assertEqual(list(second.iterdir()), [])


if __name__ == "__main__":
    unittest.main()

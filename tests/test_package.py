"""Package metadata smoke tests."""

import unittest

import linux_performance_doctor


class TestPackage(unittest.TestCase):
    def test_version_is_non_empty_string(self) -> None:
        self.assertIsInstance(linux_performance_doctor.__version__, str)
        self.assertTrue(linux_performance_doctor.__version__)


if __name__ == "__main__":
    unittest.main()

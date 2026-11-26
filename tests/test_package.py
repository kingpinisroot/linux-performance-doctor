"""Minimal package smoke tests for the initial repository skeleton.

Additional collector, CLI, and JSON output tests will be added alongside
the imported Linux Performance Doctor source code.
"""

import unittest

import linux_performance_doctor


class TestPackageSkeleton(unittest.TestCase):
    """Verify basic package importability for the repository skeleton."""

    def test_version_is_non_empty_string(self) -> None:
        self.assertIsInstance(linux_performance_doctor.__version__, str)
        self.assertTrue(len(linux_performance_doctor.__version__) > 0)


if __name__ == "__main__":
    unittest.main()

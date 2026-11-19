import contextlib
import io
import unittest
from unittest.mock import patch

from vibe_using.cli import main, parser


class CliTests(unittest.TestCase):
    def test_help_parser(self):
        self.assertEqual(parser().parse_args(["--scan-pid", "123"]).scan_pid, 123)

    def test_non_windows_scan_is_rejected(self):
        with patch("vibe_using.cli.sys.platform", "linux"):
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(["--scan-pid", "42"]), 2)

    def test_non_windows_gui_is_rejected(self):
        with patch("vibe_using.cli.sys.platform", "linux"):
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main([]), 2)


if __name__ == "__main__":
    unittest.main()

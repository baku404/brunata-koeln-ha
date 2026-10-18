"""Verify masked terminal input without using a real password or keyboard."""

import io
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts.check_portal import prompt_password


class PasswordPromptTests(unittest.TestCase):
    def prompt(self, characters):
        output = io.StringIO()
        keyboard = SimpleNamespace(getwch=Mock(side_effect=characters))
        with (
            patch("sys.platform", "win32"),
            patch("sys.stdin.isatty", return_value=True),
            patch.dict("sys.modules", {"msvcrt": keyboard}),
            redirect_stdout(output),
        ):
            result = prompt_password()
        return result, output.getvalue()

    def test_mask_and_backspace_preserve_password_without_echoing_it(self):
        result, output = self.prompt(list("sex") + ["\b"] + list("cret") + ["\r"])
        self.assertEqual(result, "secret")
        self.assertNotIn("secret", output)
        self.assertIn("*", output)

    def test_arrow_keys_do_not_become_password_characters(self):
        result, _ = self.prompt(["a", "\x00", "K", "b", "\r"])
        self.assertEqual(result, "ab")

    def test_control_c_cancels_input(self):
        with self.assertRaises(KeyboardInterrupt):
            self.prompt(["a", "\x03"])

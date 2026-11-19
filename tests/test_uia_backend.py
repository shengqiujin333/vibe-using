import unittest

from vibe_using.uia_backend import UiaAdapter


class DummyControl:
    def __init__(self, role, name, password=False):
        self.ControlTypeName = role
        self.Name = name
        self.IsPassword = password
        self.AutomationId = "example"
        self.ClassName = "Window"
        self.IsEnabled = True
        self.IsOffscreen = False
        self.AccessKey = ""
        self.AcceleratorKey = ""
        self.BoundingRectangle = None


class UiaPrivacyTests(unittest.TestCase):
    def adapter(self, include_text=False):
        # Test the property reader without initializing actual Windows COM.
        adapter = object.__new__(UiaAdapter)
        adapter.include_text = include_text
        return adapter

    def test_default_redacts_text_names(self):
        for role in ("TextControl", "EditControl", "DocumentControl"):
            result = self.adapter().describe(DummyControl(role, "private text"))
            self.assertEqual(result["name"], "")
        result = self.adapter().describe(DummyControl("ButtonControl", "Export"))
        self.assertEqual(result["name"], "Export")

    def test_explicit_include_text(self):
        result = self.adapter(True).describe(DummyControl("TextControl", "a helpful label"))
        self.assertEqual(result["name"], "a helpful label")

    def test_password_is_never_saved(self):
        result = self.adapter(True).describe(DummyControl("EditControl", "secret", password=True))
        self.assertEqual(result["name"], "")


if __name__ == "__main__":
    unittest.main()

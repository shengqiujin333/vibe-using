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

    def test_default_captures_label_text_but_redacts_edit_and_document(self):
        result = self.adapter().describe(DummyControl("TextControl", "文件"))
        self.assertEqual(result["name"], "文件")
        self.assertEqual(result["name_source"], "uia_name")
        for role in ("EditControl", "DocumentControl"):
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

class UiaEvidenceTests(unittest.TestCase):
    def adapter(self):
        adapter = object.__new__(UiaAdapter)
        adapter.include_text = False
        return adapter

    def test_label_help_and_pattern_discovery_is_read_only(self):
        class Caption:
            Name = "开始导出"

        class Control(DummyControl):
            def __init__(self):
                super().__init__("ButtonControl", "")
                self.LabeledBy = Caption()
                self.HelpText = "输出当前工程的文件"
                self.call_count = 0

            def GetInvokePattern(self):
                self.call_count += 1
                return object()

        ctrl = Control()
        info = self.adapter().describe(ctrl)
        self.assertEqual(info["name"], "开始导出")
        self.assertEqual(info["name_source"], "labeled_by")
        self.assertEqual(info["help_text"], "输出当前工程的文件")
        self.assertIn("Invoke", info["supported_patterns"])
        self.assertEqual(ctrl.call_count, 1)

    def test_edit_uses_external_label_without_leaking_content(self):
        class Label:
            Name = "查找文件"

        ctrl = DummyControl("EditControl", "sensitive input text")
        ctrl.LabeledBy = Label()
        info = self.adapter().describe(ctrl)
        self.assertEqual(info["raw_name"], "")
        self.assertEqual(info["name"], "查找文件")
        self.assertEqual(info["name_source"], "labeled_by")

    def test_legacy_accessible_fallback(self):
        class Legacy:
            Name = "生成文件"
            DefaultAction = "按下"

        class Control(DummyControl):
            def GetLegacyIAccessiblePattern(self):
                return Legacy()

        info = self.adapter().describe(Control("ButtonControl", ""))
        self.assertEqual(info["name"], "生成文件")
        self.assertEqual(info["legacy_action"], "按下")
        self.assertEqual(info["name_source"], "legacy_accessible")

    def test_password_never_reads_labeled_by_or_help(self):
        ctrl = DummyControl("EditControl", "PASSWORD", password=True)
        ctrl.LabeledBy = type("Label", (), {"Name": "secret"})()
        ctrl.HelpText = "Password hint secret"
        info = self.adapter().describe(ctrl)
        self.assertEqual(info["name"], "")
        self.assertEqual(info["help_text"], "")
        self.assertEqual(info["labeled_by"], "")

import unittest

from backend.orchestrator.project_orchestrator import _validate_preview_usability


class P8F2PreviewUsabilityTests(unittest.TestCase):
    def test_counter_app_passes_usability_contract(self):
        ok, error = _validate_preview_usability(
            prompt_text="Generate a simple counter app",
            body_text="Counter Count 0",
            root_text="Counter Count 0",
            root_child_count=1,
            interactive_count=1,
        )

        self.assertTrue(ok, error)

    def test_todo_app_passes_usability_contract(self):
        ok, error = _validate_preview_usability(
            prompt_text="Generate a todo app",
            body_text="Todo List Task Add task",
            root_text="Todo List Task Add task",
            root_child_count=1,
            interactive_count=2,
        )

        self.assertTrue(ok, error)

    def test_crud_app_passes_usability_contract(self):
        ok, error = _validate_preview_usability(
            prompt_text="Generate a CRUD MVP",
            body_text="CRUD MVP Create record Sample item Delete",
            root_text="CRUD MVP Create record Sample item Delete",
            root_child_count=1,
            interactive_count=3,
        )

        self.assertTrue(ok, error)

    def test_placeholder_page_fails_usability_contract(self):
        ok, error = _validate_preview_usability(
            prompt_text="Generate a simple counter app",
            body_text="Hello World",
            root_text="Hello World",
            root_child_count=1,
            interactive_count=0,
        )

        self.assertFalse(ok)
        self.assertIn("placeholder", error or "")

    def test_marker_only_page_fails_usability_contract(self):
        ok, error = _validate_preview_usability(
            prompt_text="Generate a todo app",
            body_text="",
            root_text="",
            root_child_count=1,
            interactive_count=0,
        )

        self.assertFalse(ok)
        self.assertIn("meaningful visible content", error or "")

    def test_empty_page_fails_usability_contract(self):
        ok, error = _validate_preview_usability(
            prompt_text="Generate a CRUD MVP",
            body_text="",
            root_text="",
            root_child_count=0,
            interactive_count=0,
        )

        self.assertFalse(ok)
        self.assertIn("no mounted children", error or "")


if __name__ == "__main__":
    unittest.main()

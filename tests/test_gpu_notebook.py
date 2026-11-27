import ast
import json
import unittest
from pathlib import Path


class GpuNotebookTests(unittest.TestCase):
    def test_notebook_is_valid_and_code_cells_compile(self):
        notebook_path = Path(__file__).parents[1] / "notebooks" / "Kling_Class_GPU_Worker.ipynb"
        notebook = json.loads(notebook_path.read_text(encoding="utf-8"))

        self.assertEqual(notebook["nbformat"], 4)
        code_cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
        self.assertGreaterEqual(len(code_cells), 3)
        for index, cell in enumerate(code_cells):
            source = "".join(cell["source"])
            compile(
                source,
                f"{notebook_path.name}:cell-{index}",
                "exec",
                flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
            )

    def test_notebook_keeps_bot_credentials_runtime_only_and_checks_webhook(self):
        notebook_path = Path(__file__).parents[1] / "notebooks" / "Kling_Class_GPU_Worker.ipynb"
        notebook_text = notebook_path.read_text(encoding="utf-8")

        self.assertIn("getpass.getpass", notebook_text)
        self.assertIn("getWebhookInfo", notebook_text)
        self.assertIn("ALLOWED_CHAT_ID", notebook_text)
        self.assertNotIn("123456789:ABC", notebook_text)
        self.assertIn("CINEMA_JOB_ID", notebook_text)
        self.assertIn("uuid.uuid4().hex", notebook_text)
        self.assertIn("hashlib.sha256", notebook_text)
        self.assertIn("prepare_social_package", notebook_text)
        self.assertIn("deliver_video", notebook_text)
        self.assertNotIn("4200 + idx", notebook_text)


if __name__ == "__main__":
    unittest.main()

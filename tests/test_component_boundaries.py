from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "docs" / "architecture" / "component-manifest.json"


def _python_files(path: Path):
    if path.is_file() and path.suffix == ".py":
        yield path
    elif path.is_dir():
        yield from sorted(path.rglob("*.py"))


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
    return found


class ComponentBoundaryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_declared_component_paths_exist(self) -> None:
        for component, spec in self.manifest["components"].items():
            for rel in spec["paths"]:
                with self.subTest(component=component, path=rel):
                    self.assertTrue((REPO_ROOT / rel).exists(), rel)

    def test_review_projection_has_no_reverse_runtime_dependencies(self) -> None:
        rules = self.manifest["enforced_rules"]
        forbidden = tuple(rules["review_projection_forbidden_import_prefixes"])
        projection = self.manifest["components"]["review_projection"]

        violations: list[str] = []
        for rel in projection["paths"]:
            root = REPO_ROOT / rel
            for path in _python_files(root):
                for imported in _imports(path):
                    if any(imported == prefix or imported.startswith(prefix + ".") for prefix in forbidden):
                        violations.append(f"{path.relative_to(REPO_ROOT)} imports {imported}")
        self.assertEqual(violations, [])

    def test_review_projection_does_not_encode_consumer_identity(self) -> None:
        forbidden_text = self.manifest["enforced_rules"]["review_projection_forbidden_text"]
        violations: list[str] = []
        for rel in self.manifest["components"]["review_projection"]["paths"]:
            root = REPO_ROOT / rel
            for path in _python_files(root):
                text = path.read_text(encoding="utf-8").lower()
                for token in forbidden_text:
                    if token.lower() in text:
                        violations.append(f"{path.relative_to(REPO_ROOT)} contains {token}")
        self.assertEqual(violations, [])

    def test_review_projection_is_not_owned_by_backend_exports(self) -> None:
        projection_paths = set(self.manifest["components"]["review_projection"]["paths"])
        self.assertIn("pipeline/projections", projection_paths)
        self.assertNotIn("backend/exports", projection_paths)
        compatibility_paths = set(self.manifest["components"]["compatibility_surfaces"]["paths"])
        self.assertIn("backend/exports/export_review_csv.py", compatibility_paths)


if __name__ == "__main__":
    unittest.main()

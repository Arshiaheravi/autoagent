#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test gap detector — auto-discover untested public functions.

Pure function: parses AST of changed .py files, checks for corresponding
test_* functions in sibling test files. No side effects.
"""
import ast
from pathlib import Path
from typing import List


def detect_test_gaps(changed_files: List[str]) -> List[dict]:
    """Find public functions in changed files that lack a corresponding test.

    For each source file, looks for a sibling test_<module>.py and checks
    whether each public function has at least one test_* function whose name
    contains the function name.

    Returns list of dicts: {function, file, has_test: False}
    """
    gaps = []
    for file_path in changed_files:
        path = Path(file_path)

        # Skip non-Python, test files, and __init__
        if path.suffix != ".py":
            continue
        if path.name.startswith("test_"):
            continue
        if path.name == "__init__.py":
            continue

        # Extract public function names via AST
        public_funcs = _extract_public_functions(path)
        if not public_funcs:
            continue

        # Find corresponding test file
        test_file = path.parent / f"test_{path.name}"
        test_funcs = _extract_test_function_names(test_file) if test_file.exists() else set()

        # Check each public function for coverage
        for func_name in public_funcs:
            if not _has_matching_test(func_name, test_funcs):
                gaps.append({
                    "function": func_name,
                    "file": str(path),
                    "has_test": False,
                })

    return gaps


def _extract_public_functions(path: Path) -> List[str]:
    """Parse a Python file and return names of public top-level functions."""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, OSError):
        return []

    funcs = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            funcs.append(node.name)
    return funcs


def _extract_test_function_names(test_path: Path) -> set:
    """Parse a test file and return set of test_* function names."""
    try:
        source = test_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(test_path))
    except (SyntaxError, OSError):
        return set()

    names = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            names.add(node.name)
    return names


def _has_matching_test(func_name: str, test_funcs: set) -> bool:
    """Check if any test function name contains the function name."""
    return any(func_name in t for t in test_funcs)

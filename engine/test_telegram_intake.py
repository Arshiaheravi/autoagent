"""Tests for telegram_intake — project-name uniqueness (no tenant collision)."""
from unittest.mock import patch

import pytest

telegram_intake = pytest.importorskip("telegram_intake")


def test_unique_name_free():
    with patch("registry.list_projects", return_value=[]):
        assert telegram_intake._unique_project_name("newapp") == "newapp"


def test_unique_name_suffixes_on_collision():
    with patch("registry.list_projects",
               return_value=[{"name": "build-a-marketplace"}]):
        assert telegram_intake._unique_project_name("build-a-marketplace") == "build-a-marketplace-2"


def test_unique_name_walks_past_taken_suffixes():
    with patch("registry.list_projects",
               return_value=[{"name": "shop"}, {"name": "shop-2"}, {"name": "shop-3"}]):
        assert telegram_intake._unique_project_name("shop") == "shop-4"


def test_unique_name_degrades_gracefully_without_registry():
    with patch("registry.list_projects", side_effect=RuntimeError("no registry")):
        assert telegram_intake._unique_project_name("anything") == "anything"

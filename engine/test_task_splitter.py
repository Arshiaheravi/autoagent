"""Tests for task_splitter.estimate_complexity — TDD first."""

from task_splitter import estimate_complexity


class TestEstimateSimpleTask:
    """Simple tasks should have low complexity and no splits."""

    def test_single_file_low_complexity(self):
        task = (
            "### Fix typo in dashboard title\n"
            "- When: dashboard renders\n"
            "- Files: engine/dashboard_server.py\n"
            "- Tests: test_dashboard_title_correct\n"
        )
        result = estimate_complexity(task)
        assert result["score"] <= 3
        assert result["should_split"] is False
        assert result["subtasks"] == []

    def test_no_files_mentioned(self):
        task = "Fix the bug in the login page"
        result = estimate_complexity(task)
        assert "score" in result
        assert "should_split" in result
        assert isinstance(result["subtasks"], list)

    def test_returns_dict_with_required_keys(self):
        result = estimate_complexity("Simple one-liner fix")
        assert set(result.keys()) >= {"score", "should_split", "subtasks", "reason"}


class TestEstimateComplexTaskSplits:
    """Complex tasks (many files, criteria, keywords) should be split."""

    def test_many_files_triggers_split(self):
        task = (
            "### Add new analytics pipeline\n"
            "- Files: engine/analytics.py, engine/dashboard.py, "
            "engine/routes.py, engine/models.py, engine/services.py, "
            "engine/tests.py\n"
            "- Tests: test_analytics_pipeline, test_dashboard_update, "
            "test_route_wiring, test_model_fields\n"
        )
        result = estimate_complexity(task)
        assert result["score"] >= 5
        assert result["should_split"] is True
        assert len(result["subtasks"]) >= 2

    def test_many_acceptance_criteria_triggers_split(self):
        task = (
            "### Build full auth system\n"
            "- Tests: test_register_user, test_login_user, test_logout_user, "
            "test_password_reset, test_email_verification, test_token_refresh, "
            "test_admin_guard\n"
            "- Files: engine/auth.py, engine/routes.py\n"
        )
        result = estimate_complexity(task)
        assert result["score"] >= 5
        assert result["should_split"] is True

    def test_complex_keywords_increase_score(self):
        task = (
            "### Migrate database schema and refactor ORM layer\n"
            "- Requires: migration, refactor, rewrite of existing models\n"
            "- Files: engine/models.py, engine/db.py, engine/migration.py\n"
        )
        result = estimate_complexity(task)
        # Keywords like migrate, refactor, rewrite should boost score
        assert result["score"] >= 4


class TestEstimateWithFileList:
    """File count is a primary complexity signal."""

    def test_one_file_scores_low(self):
        task = "- Files: engine/foo.py"
        result = estimate_complexity(task)
        assert result["file_count"] == 1
        assert result["score"] <= 3

    def test_four_files_scores_medium(self):
        task = "- Files: engine/a.py, engine/b.py, engine/c.py, engine/d.py"
        result = estimate_complexity(task)
        assert result["file_count"] == 4
        assert 3 <= result["score"] <= 6

    def test_six_files_scores_high(self):
        task = (
            "- Files: engine/a.py, engine/b.py, engine/c.py, "
            "engine/d.py, engine/e.py, engine/f.py"
        )
        result = estimate_complexity(task)
        assert result["file_count"] == 6
        assert result["score"] >= 5
        assert result["should_split"] is True

    def test_subtasks_contain_file_subsets(self):
        task = (
            "### Big feature\n"
            "- Files: engine/a.py, engine/b.py, engine/c.py, "
            "engine/d.py, engine/e.py, engine/f.py\n"
            "- Tests: test_a, test_b, test_c, test_d, test_e, test_f\n"
        )
        result = estimate_complexity(task)
        assert result["should_split"] is True
        for sub in result["subtasks"]:
            assert isinstance(sub, str)
            assert len(sub) > 0

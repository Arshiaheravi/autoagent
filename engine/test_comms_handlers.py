"""Tests for comms_handlers.py — command handling + background listener split from comms.py."""
from unittest.mock import patch, MagicMock
import comms_handlers


def test_comms_handlers_importable():
    """comms_handlers module exists and is importable."""
    assert hasattr(comms_handlers, '_handle_command')
    assert hasattr(comms_handlers, 'start_listener')
    assert hasattr(comms_handlers, '_background_listener')


def test_comms_handlers_under_300_lines():
    """comms_handlers.py must stay under the 300-line hard rule."""
    import inspect, pathlib
    src = pathlib.Path(inspect.getfile(comms_handlers))
    line_count = len(src.read_text().splitlines())
    assert line_count <= 300, f"comms_handlers.py is {line_count} lines (max 300)"


def test_comms_under_300_lines():
    """comms.py must stay under 300 lines after the split."""
    import inspect, pathlib, comms
    src = pathlib.Path(inspect.getfile(comms))
    line_count = len(src.read_text().splitlines())
    assert line_count <= 300, f"comms.py is {line_count} lines (max 300)"


def test_handle_command_pause():
    """_handle_command('/pause') calls set_paused(True)."""
    mock_comms = MagicMock()
    with patch.object(comms_handlers, '_get_comms', return_value=mock_comms):
        comms_handlers._handle_command("/pause")
    mock_comms.set_paused.assert_called_once_with(True)
    mock_comms._send.assert_called_once()


def test_handle_command_resume():
    """_handle_command('/resume') calls set_paused(False)."""
    mock_comms = MagicMock()
    with patch.object(comms_handlers, '_get_comms', return_value=mock_comms):
        comms_handlers._handle_command("/resume")
    mock_comms.set_paused.assert_called_once_with(False)
    mock_comms._send.assert_called_once()


def test_handle_command_help():
    """_handle_command('/help') sends help text."""
    mock_comms = MagicMock()
    with patch.object(comms_handlers, '_get_comms', return_value=mock_comms):
        comms_handlers._handle_command("/help")
    sent_text = mock_comms._send.call_args[0][0]
    assert "Commands" in sent_text


def test_handle_command_unknown():
    """_handle_command with unknown command sends error."""
    mock_comms = MagicMock()
    with patch.object(comms_handlers, '_get_comms', return_value=mock_comms):
        comms_handlers._handle_command("/foobar")
    sent_text = mock_comms._send.call_args[0][0]
    assert "Unknown" in sent_text


def test_backward_compat_reexports():
    """comms.py re-exports _handle_command, start_listener for backward compat."""
    import comms
    assert hasattr(comms, '_handle_command')
    assert hasattr(comms, 'start_listener')
    assert comms._handle_command is comms_handlers._handle_command
    assert comms.start_listener is comms_handlers.start_listener


# ── Interactive Planning Tests ──────────────────────────────────


def test_format_plan_message_basic(tmp_path):
    """format_plan_message formats current_task.md into Telegram-friendly text."""
    from session_hooks import format_plan_message
    plan = (
        "# Current Task: Add login page\n"
        "Steps: 3 total | 3 remaining\n"
        "- [ ] Write tests\n"
        "- [ ] Implement login route\n"
        "- [ ] Add frontend form\n"
    )
    msg = format_plan_message(plan)
    assert "Add login page" in msg
    assert "1." in msg  # numbered steps
    assert "Write tests" in msg
    assert "Implement login route" in msg
    assert "Add frontend form" in msg


def test_format_plan_message_with_done_steps():
    """format_plan_message shows checked steps as done."""
    from session_hooks import format_plan_message
    plan = (
        "# Current Task: Fix bug\n"
        "Steps: 3 total | 1 remaining\n"
        "- [x] Reproduce the bug\n"
        "- [x] Write failing test\n"
        "- [ ] Fix the root cause\n"
    )
    msg = format_plan_message(plan)
    assert "Fix bug" in msg
    # Done steps should be marked differently from pending
    assert "✅" in msg or "✓" in msg or "done" in msg.lower()


def test_format_plan_message_empty():
    """format_plan_message returns empty string for no-task content."""
    from session_hooks import format_plan_message
    assert format_plan_message("# No current task") == ""
    assert format_plan_message("") == ""


def test_parse_plan_edit_remove_step():
    """parse_plan_edit with 'remove 2' removes the 2nd step."""
    from session_hooks import parse_plan_edit
    plan = (
        "# Current Task: Build feature\n"
        "Steps: 3 total | 3 remaining\n"
        "- [ ] Step one\n"
        "- [ ] Step two\n"
        "- [ ] Step three\n"
    )
    result = parse_plan_edit(plan, "remove 2")
    assert "Step one" in result
    assert "Step two" not in result
    assert "Step three" in result
    assert "2 total" in result


def test_parse_plan_edit_add_step():
    """parse_plan_edit with 'add: New step' appends a step."""
    from session_hooks import parse_plan_edit
    plan = (
        "# Current Task: Build feature\n"
        "Steps: 2 total | 2 remaining\n"
        "- [ ] Step one\n"
        "- [ ] Step two\n"
    )
    result = parse_plan_edit(plan, "add: Write integration test")
    assert "Write integration test" in result
    assert "3 total" in result


def test_parse_plan_edit_reorder():
    """parse_plan_edit with 'move 3 to 1' reorders steps."""
    from session_hooks import parse_plan_edit
    plan = (
        "# Current Task: Build feature\n"
        "Steps: 3 total | 3 remaining\n"
        "- [ ] Step one\n"
        "- [ ] Step two\n"
        "- [ ] Step three\n"
    )
    result = parse_plan_edit(plan, "move 3 to 1")
    lines = [l for l in result.splitlines() if l.startswith("- [")]
    assert "Step three" in lines[0]
    assert "Step one" in lines[1]
    assert "Step two" in lines[2]


def test_parse_plan_edit_full_replacement():
    """parse_plan_edit with markdown list replaces all steps."""
    from session_hooks import parse_plan_edit
    plan = (
        "# Current Task: Build feature\n"
        "Steps: 2 total | 2 remaining\n"
        "- [ ] Old step one\n"
        "- [ ] Old step two\n"
    )
    replacement = "- [ ] New first\n- [ ] New second\n- [ ] New third"
    result = parse_plan_edit(plan, replacement)
    assert "Old step" not in result
    assert "New first" in result
    assert "New second" in result
    assert "New third" in result
    assert "3 total" in result


def test_parse_plan_edit_approve():
    """parse_plan_edit with 'ok' or 'approve' returns plan unchanged."""
    from session_hooks import parse_plan_edit
    plan = (
        "# Current Task: Build feature\n"
        "Steps: 2 total | 2 remaining\n"
        "- [ ] Step one\n"
        "- [ ] Step two\n"
    )
    assert parse_plan_edit(plan, "ok") == plan
    assert parse_plan_edit(plan, "approve") == plan
    assert parse_plan_edit(plan, "LGTM") == plan


def test_handle_command_plan(tmp_path):
    """_handle_command('/plan') sends the current plan via Telegram."""
    plan_text = (
        "# Current Task: Test task\n"
        "Steps: 2 total | 2 remaining\n"
        "- [ ] Step A\n"
        "- [ ] Step B\n"
    )
    plan_file = tmp_path / "current_task.md"
    plan_file.write_text(plan_text)

    mock_comms = MagicMock()
    with patch.object(comms_handlers, '_get_comms', return_value=mock_comms), \
         patch.object(comms_handlers, '_get_current_task_path', return_value=plan_file):
        comms_handlers._handle_command("/plan")
    mock_comms._send.assert_called_once()
    sent = mock_comms._send.call_args[0][0]
    assert "Test task" in sent
    assert "Step A" in sent


def test_propose_plan_no_reply(tmp_path):
    """propose_plan sends plan and returns None on timeout (no edit)."""
    plan_text = (
        "# Current Task: Test task\n"
        "Steps: 1 total | 1 remaining\n"
        "- [ ] Do thing\n"
    )
    plan_file = tmp_path / "current_task.md"
    plan_file.write_text(plan_text)

    with patch("comms_handlers._get_comms") as mock_gc:
        mock_comms = MagicMock()
        mock_comms.ask.return_value = None  # timeout
        mock_gc.return_value = mock_comms
        result = comms_handlers.propose_plan(plan_file, project="test", timeout=1)
    assert result is None
    # Plan file unchanged
    assert plan_file.read_text() == plan_text


def test_propose_plan_with_edit(tmp_path):
    """propose_plan applies user's edit reply to current_task.md."""
    plan_text = (
        "# Current Task: Test task\n"
        "Steps: 2 total | 2 remaining\n"
        "- [ ] Step one\n"
        "- [ ] Step two\n"
    )
    plan_file = tmp_path / "current_task.md"
    plan_file.write_text(plan_text)

    with patch("comms_handlers._get_comms") as mock_gc:
        mock_comms = MagicMock()
        mock_comms.ask.return_value = "add: Step three"
        mock_gc.return_value = mock_comms
        result = comms_handlers.propose_plan(plan_file, project="test", timeout=1)
    assert result is not None
    updated = plan_file.read_text()
    assert "Step three" in updated
    assert "3 total" in updated

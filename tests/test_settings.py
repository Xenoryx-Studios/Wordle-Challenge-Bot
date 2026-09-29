from core.settings import build_intents, reminders_enabled


def test_message_content_is_not_requested_without_the_setting():
    assert not reminders_enabled({})
    assert build_intents({}).message_content is False


def test_message_content_is_requested_when_reminders_are_enabled():
    for value in ("1", "true", "YES", "on"):
        assert reminders_enabled({"ENABLE_REMINDERS": value})
        assert build_intents({"ENABLE_REMINDERS": value}).message_content is True


def test_other_values_leave_reminders_off():
    assert not reminders_enabled({"ENABLE_REMINDERS": "0"})
    assert build_intents({"ENABLE_REMINDERS": "no"}).message_content is False

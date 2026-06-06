"""Unit tests for manual pause control."""

from chcp.core.pause_control import PauseController, get_pause_controller


class TestPauseController:
    def test_request_and_clear_pause(self):
        controller = PauseController()
        assert not controller.is_pause_requested()
        controller.request_pause()
        assert controller.is_pause_requested()
        controller._pause_requested.clear()
        assert not controller.is_pause_requested()

    def test_get_pause_controller_returns_singleton(self):
        first = get_pause_controller()
        second = get_pause_controller()
        assert first is second

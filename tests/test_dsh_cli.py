"""Plugin topics must never dispatch login/setup or change research into hot mode."""
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import last30days


@pytest.mark.parametrize("topic", ["setup", "login", "登录", "hot", "trending", "热榜", "--diagnose"])
def test_literal_research_topic_does_not_dispatch_commands(monkeypatch, topic):
    monkeypatch.setattr(sys, "argv", ["last30days.py", "--literal-topic", "--", topic])
    monkeypatch.setattr(last30days.env, "get_config", lambda: {})
    for name in ("_run_login", "_run_hot"):
        monkeypatch.setattr(last30days, name, Mock(side_effect=AssertionError("unexpected command")))
    monkeypatch.setattr(last30days.setup_wizard, "run_auto_setup", Mock(side_effect=AssertionError("unexpected setup")))
    reached = Mock(side_effect=RuntimeError("research reached"))
    monkeypatch.setattr(last30days.dates, "get_date_range", reached)
    with pytest.raises(RuntimeError, match="research reached"):
        last30days.main()
    reached.assert_called_once()


@pytest.mark.parametrize("topic", ["setup", "login", "hot", "--diagnose"])
def test_literal_hot_filter_is_preserved(monkeypatch, topic):
    monkeypatch.setattr(sys, "argv", ["last30days.py", "--hot", "--literal-topic", "--", topic])
    monkeypatch.setattr(last30days.env, "get_config", lambda: {})
    monkeypatch.setattr(last30days, "_install_global_timeout", lambda _: None)
    run = Mock(return_value=0)
    monkeypatch.setattr(last30days, "_run_hot", run)
    with pytest.raises(SystemExit) as exc:
        last30days.main()
    assert exc.value.code == 0
    assert run.call_args[0][1] == topic

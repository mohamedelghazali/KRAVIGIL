import pytest

from agents.communication.agent_client import AgentClient


def test_agent_client_rejects_remote_control_plane_over_plain_http():
    with pytest.raises(ValueError, match="must use HTTPS"):
        AgentClient("http://control.example.test")

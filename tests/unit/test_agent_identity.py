import stat

from agents.identity.identity_manager import IdentityManager


def test_agent_identity_is_reused_across_restarts(tmp_path):
    first = IdentityManager(agent_dir=str(tmp_path))
    first_fingerprint, first_public_key = first.generate_identity("kravigil-agent")

    second = IdentityManager(agent_dir=str(tmp_path))
    second_fingerprint, second_public_key = second.generate_identity("kravigil-agent")

    assert second_fingerprint == first_fingerprint
    assert second_public_key == first_public_key
    assert stat.S_IMODE(second.key_path and __import__("os").stat(second.key_path).st_mode) == 0o600


def test_agent_identity_fails_closed_when_key_and_certificate_do_not_match(tmp_path):
    identity = IdentityManager(agent_dir=str(tmp_path))
    identity.generate_identity("kravigil-agent")
    with open(identity.key_path, "wb") as key_file:
        key_file.write(b"not-the-private-key")

    try:
        identity.generate_identity("kravigil-agent")
    except (ValueError, TypeError):
        pass
    else:
        raise AssertionError("Mismatched/corrupt identity must not be silently replaced")

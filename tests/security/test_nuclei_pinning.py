from backend.services.normalization.adapters.nuclei import NucleiAdapter


def test_pinned_https_scan_preserves_host_and_sni(monkeypatch):
    adapter = NucleiAdapter()
    captured = {}

    def fake_execute(args, should_cancel=None):
        captured["args"] = args
        return ""

    monkeypatch.setattr(adapter, "execute", fake_execute)
    adapter.scan("https://example.com:8443/login", pinned_ip="93.184.216.34")
    args = captured["args"]
    assert args[1] == "https://93.184.216.34:8443/login"
    assert args[args.index("-H") + 1] == "Host: example.com:8443"
    assert args[args.index("-sni") + 1] == "example.com"
    assert "-disable-redirects" in args

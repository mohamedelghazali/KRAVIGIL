from backend.core import telemetry


def test_setup_telemetry_registers_exporter_shutdown(monkeypatch):
    registered = []

    monkeypatch.setattr(telemetry.atexit, "register", registered.append)
    monkeypatch.setattr(telemetry.trace, "set_tracer_provider", lambda provider: None)
    monkeypatch.setattr(telemetry.FastAPIInstrumentor, "instrument_app", lambda app: None)
    monkeypatch.setattr(
        telemetry.SQLAlchemyInstrumentor,
        "instrument",
        lambda self, engine: None,
    )

    provider = telemetry.setup_telemetry(object())

    shutdown_callbacks = [
        callback
        for callback in registered
        if getattr(callback, "__self__", None) is provider
    ]
    assert shutdown_callbacks
    shutdown_callbacks[-1]()

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

    assert len(registered) == 1
    assert registered[0].__self__ is provider
    registered[0]()

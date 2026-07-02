import notify


def test_format_notification_error():
    assert notify.format_notification("error", "boom") == "::error::[scrape] boom"


def test_format_notification_warning():
    assert notify.format_notification("warning", "slow") == "::warning::[scrape] slow"


def test_format_notification_unknown_kind_defaults_to_notice():
    assert notify.format_notification("bogus", "hi") == "::notice::[scrape] hi"


def test_emit_writes_to_stream(capsys):
    notify.emit("error", "down")
    assert "::error::[scrape] down" in capsys.readouterr().out


def test_main_returns_zero_and_emits(capsys):
    rc = notify.main(["--kind", "warning", "--message", "heads up"])
    assert rc == 0
    assert "::warning::[scrape] heads up" in capsys.readouterr().out


def test_format_notification_collapses_newlines_no_spoof():
    out = notify.format_notification("warning", "ok\n::error::spoofed")
    assert "\n" not in out
    assert "\n::error::" not in out  # no second annotation line injected
    assert out == "::warning::[scrape] ok ::error::spoofed"

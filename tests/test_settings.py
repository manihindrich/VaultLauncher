from vault_launcher.settings import Settings, load_settings, save_settings


def test_defaults_when_missing(tmp_path):
    assert load_settings(tmp_path / "settings.json") == Settings()


def test_roundtrip(tmp_path):
    path = tmp_path / "sub" / "settings.json"
    settings = Settings(theme="dark", close_after_open=False, sort_mode="label", window_geometry="AA==")
    save_settings(path, settings)
    assert load_settings(path) == settings


def test_invalid_values_fall_back(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"theme": "neon", "close_after_open": "yes", "sort_mode": 3, "extra": 1}')
    assert load_settings(path) == Settings()


def test_broken_file_gives_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{oops")
    assert load_settings(path) == Settings()

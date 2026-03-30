import aitext.load_env as load_env_mod


def test_load_env_missing_no_crash(tmp_path, monkeypatch):
    monkeypatch.setattr(load_env_mod, "_ENV_PATH", tmp_path / "no_such_env")
    load_env_mod.load_env()

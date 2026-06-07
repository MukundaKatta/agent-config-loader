"""Tests for agent-config-loader."""

from __future__ import annotations

import pytest

from agent_config_loader import AgentConfig, ConfigField, ConfigLoadError, field

# ---------------------------------------------------------------------------
# ConfigField
# ---------------------------------------------------------------------------


def test_field_defaults_to_str():
    f = ConfigField()
    assert f.type is str
    assert f.required is True


def test_field_with_default():
    f = ConfigField(str, "hello")
    assert f.required is False
    assert f.default == "hello"


def test_field_required_when_no_default():
    f = ConfigField(int)
    assert f.required is True


def test_field_bool_not_required():
    f = field(bool, False)
    assert f.required is False


def test_field_repr():
    f = field(int, 5)
    assert "int" in repr(f)
    assert "5" in repr(f)


def test_field_repr_required():
    f = field(int)
    r = repr(f)
    assert "int" in r
    assert "required" in r


# ---------------------------------------------------------------------------
# ConfigField.coerce
# ---------------------------------------------------------------------------


def test_coerce_str():
    f = ConfigField(str)
    assert f.coerce("hello") == "hello"


def test_coerce_int():
    f = ConfigField(int)
    assert f.coerce("42") == 42


def test_coerce_float():
    f = ConfigField(float)
    assert f.coerce("3.14") == pytest.approx(3.14)


def test_coerce_bool_true_values():
    f = ConfigField(bool)
    for raw in ("1", "true", "True", "TRUE", "yes", "YES", "on", "ON"):
        assert f.coerce(raw) is True


def test_coerce_bool_false_values():
    f = ConfigField(bool)
    for raw in ("0", "false", "no", "off", "", "anything"):
        assert f.coerce(raw) is False


def test_coerce_int_bad_value_raises():
    f = ConfigField(int)
    with pytest.raises(ValueError):
        f.coerce("notanint")


# ---------------------------------------------------------------------------
# ConfigLoadError
# ---------------------------------------------------------------------------


def test_config_load_error_missing():
    err = ConfigLoadError(missing=["api_key", "model"])
    assert "api_key" in str(err)
    assert err.missing == ["api_key", "model"]
    assert err.bad_types == {}


def test_config_load_error_bad_types():
    err = ConfigLoadError(bad_types={"max_tokens": "abc"})
    assert "max_tokens" in str(err)
    assert err.bad_types == {"max_tokens": "abc"}


def test_config_load_error_both():
    err = ConfigLoadError(missing=["x"], bad_types={"y": "bad"})
    assert err.missing == ["x"]
    assert err.bad_types == {"y": "bad"}


def test_config_load_error_is_value_error():
    err = ConfigLoadError(missing=["x"])
    assert isinstance(err, ValueError)


def test_config_load_error_empty_has_default_message():
    err = ConfigLoadError()
    assert err.missing == []
    assert err.bad_types == {}
    assert str(err) == "Config load error."


def test_config_load_error_copies_inputs():
    missing = ["a"]
    bad = {"b": "bad"}
    err = ConfigLoadError(missing=missing, bad_types=bad)
    missing.append("c")
    bad["d"] = "also-bad"
    assert err.missing == ["a"]
    assert err.bad_types == {"b": "bad"}


# ---------------------------------------------------------------------------
# AgentConfig.from_env — basic
# ---------------------------------------------------------------------------


def test_from_env_string_field():
    schema = {"model": field(str, "claude")}
    cfg = AgentConfig.from_env(schema, env={})
    assert cfg["model"] == "claude"


def test_from_env_env_override():
    schema = {"model": field(str, "claude")}
    cfg = AgentConfig.from_env(schema, env={"MODEL": "gpt-4"})
    assert cfg["model"] == "gpt-4"


def test_from_env_int_coercion():
    schema = {"max_tokens": field(int, 1024)}
    cfg = AgentConfig.from_env(schema, env={"MAX_TOKENS": "2048"})
    assert cfg["max_tokens"] == 2048


def test_from_env_float_coercion():
    schema = {"temperature": field(float, 0.7)}
    cfg = AgentConfig.from_env(schema, env={"TEMPERATURE": "0.9"})
    assert cfg["temperature"] == pytest.approx(0.9)


def test_from_env_bool_true():
    schema = {"verbose": field(bool, False)}
    cfg = AgentConfig.from_env(schema, env={"VERBOSE": "true"})
    assert cfg["verbose"] is True


def test_from_env_bool_false():
    schema = {"verbose": field(bool, True)}
    cfg = AgentConfig.from_env(schema, env={"VERBOSE": "false"})
    assert cfg["verbose"] is False


# ---------------------------------------------------------------------------
# AgentConfig.from_env — prefix
# ---------------------------------------------------------------------------


def test_from_env_prefix():
    schema = {"model": field(str, "default")}
    cfg = AgentConfig.from_env(schema, prefix="MYAPP_", env={"MYAPP_MODEL": "fancy"})
    assert cfg["model"] == "fancy"


def test_from_env_prefix_ignores_unprefixed():
    schema = {"model": field(str, "default")}
    cfg = AgentConfig.from_env(schema, prefix="APP_", env={"MODEL": "wrong"})
    assert cfg["model"] == "default"


# ---------------------------------------------------------------------------
# AgentConfig.from_env — missing required
# ---------------------------------------------------------------------------


def test_from_env_missing_required_raises():
    schema = {"api_key": field(str)}
    with pytest.raises(ConfigLoadError) as exc_info:
        AgentConfig.from_env(schema, env={})
    assert "api_key" in exc_info.value.missing


def test_from_env_multiple_missing_reported_together():
    schema = {"a": field(str), "b": field(int)}
    with pytest.raises(ConfigLoadError) as exc_info:
        AgentConfig.from_env(schema, env={})
    assert "a" in exc_info.value.missing
    assert "b" in exc_info.value.missing


# ---------------------------------------------------------------------------
# AgentConfig.from_env — bad types
# ---------------------------------------------------------------------------


def test_from_env_bad_type_raises():
    schema = {"port": field(int, 8080)}
    with pytest.raises(ConfigLoadError) as exc_info:
        AgentConfig.from_env(schema, env={"PORT": "notanumber"})
    assert "port" in exc_info.value.bad_types


def test_from_env_bad_type_and_missing_together():
    schema = {"required_key": field(str), "port": field(int, 80)}
    with pytest.raises(ConfigLoadError) as exc_info:
        AgentConfig.from_env(schema, env={"PORT": "bad"})
    assert "required_key" in exc_info.value.missing
    assert "port" in exc_info.value.bad_types


def test_from_env_required_field_with_bad_value_is_bad_type_not_missing():
    # A required field whose value is present but uncoercible is a coercion
    # failure, not a missing field.
    schema = {"port": field(int)}
    with pytest.raises(ConfigLoadError) as exc_info:
        AgentConfig.from_env(schema, env={"PORT": "notanint"})
    assert exc_info.value.missing == []
    assert exc_info.value.bad_types == {"port": "notanint"}


# ---------------------------------------------------------------------------
# AgentConfig access
# ---------------------------------------------------------------------------


def test_getitem():
    schema = {"x": field(int, 5)}
    cfg = AgentConfig.from_env(schema, env={})
    assert cfg["x"] == 5


def test_getitem_missing_raises_key_error():
    schema = {"x": field(int, 5)}
    cfg = AgentConfig.from_env(schema, env={})
    with pytest.raises(KeyError):
        cfg["nope"]  # type: ignore[index]


def test_get_default():
    schema = {"x": field(int, 5)}
    cfg = AgentConfig.from_env(schema, env={})
    assert cfg.get("nope", 99) == 99


def test_get_existing():
    schema = {"x": field(int, 5)}
    cfg = AgentConfig.from_env(schema, env={})
    assert cfg.get("x") == 5


def test_contains_true():
    schema = {"x": field(str, "hello")}
    cfg = AgentConfig.from_env(schema, env={})
    assert "x" in cfg


def test_contains_false():
    schema = {"x": field(str, "hello")}
    cfg = AgentConfig.from_env(schema, env={})
    assert "nope" not in cfg


def test_to_dict():
    schema = {"a": field(str, "x"), "b": field(int, 1)}
    cfg = AgentConfig.from_env(schema, env={})
    d = cfg.to_dict()
    assert d == {"a": "x", "b": 1}


def test_to_dict_is_copy():
    schema = {"a": field(str, "x")}
    cfg = AgentConfig.from_env(schema, env={})
    d = cfg.to_dict()
    d["a"] = "mutated"
    assert cfg["a"] == "x"


def test_keys():
    schema = {"z": field(str, "z"), "a": field(str, "a")}
    cfg = AgentConfig.from_env(schema, env={})
    assert cfg.keys() == ["z", "a"]  # schema order


def test_repr():
    schema = {"x": field(str, "hello")}
    cfg = AgentConfig.from_env(schema, env={})
    assert "AgentConfig" in repr(cfg)


# ---------------------------------------------------------------------------
# help
# ---------------------------------------------------------------------------


def test_help_shows_field_names():
    schema = {
        "model": field(str, "claude", description="Model name"),
        "api_key": field(str, description="API key"),
    }
    cfg = AgentConfig.from_env(schema, env={"API_KEY": "sk-test"})
    h = cfg.help()
    assert "model" in h
    assert "api_key" in h
    assert "required" in h


def test_help_shows_defaults():
    schema = {"model": field(str, "claude")}
    cfg = AgentConfig.from_env(schema, env={})
    assert "claude" in cfg.help()


def test_help_shows_description_and_type():
    schema = {"max_tokens": field(int, 1024, description="Max output tokens")}
    cfg = AgentConfig.from_env(schema, env={})
    h = cfg.help()
    assert "Max output tokens" in h
    assert "int" in h


def test_help_omits_description_when_absent():
    schema = {"model": field(str, "claude")}
    cfg = AgentConfig.from_env(schema, env={})
    assert "—" not in cfg.help()


# ---------------------------------------------------------------------------
# schema_for
# ---------------------------------------------------------------------------


def test_schema_for_returns_field():
    f = field(int, 5)
    schema = {"port": f}
    cfg = AgentConfig.from_env(schema, env={})
    assert cfg.schema_for("port").type is int


# ---------------------------------------------------------------------------
# Multiple fields end-to-end
# ---------------------------------------------------------------------------


def test_full_schema():
    schema = {
        "model": field(str, "claude-3", description="LLM model name"),
        "max_tokens": field(int, 512),
        "temperature": field(float, 0.7),
        "verbose": field(bool, False),
        "api_key": field(str, description="API key"),
    }
    env = {"API_KEY": "sk-abc", "MAX_TOKENS": "1024", "VERBOSE": "1"}
    cfg = AgentConfig.from_env(schema, env=env)
    assert cfg["model"] == "claude-3"
    assert cfg["max_tokens"] == 1024
    assert cfg["temperature"] == pytest.approx(0.7)
    assert cfg["verbose"] is True
    assert cfg["api_key"] == "sk-abc"


# ---------------------------------------------------------------------------
# from_env — default environment (os.environ)
# ---------------------------------------------------------------------------


def test_from_env_reads_os_environ_when_env_is_none(monkeypatch):
    monkeypatch.setenv("MODEL", "from-os-environ")
    schema = {"model": field(str, "default")}
    cfg = AgentConfig.from_env(schema)
    assert cfg["model"] == "from-os-environ"


# ---------------------------------------------------------------------------
# Package exports
# ---------------------------------------------------------------------------


def test_public_api_exports():
    import agent_config_loader

    assert set(agent_config_loader.__all__) == {
        "AgentConfig",
        "ConfigField",
        "ConfigLoadError",
        "field",
    }

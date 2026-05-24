# agent-config-loader

Load and validate AI agent configuration from environment variables.

Define a schema with `field()` descriptors, call `AgentConfig.from_env()`, and get typed, validated values. Missing required fields and coercion failures are reported together in a single `ConfigLoadError`.

## Install

```bash
pip install agent-config-loader
```

## Quick start

```python
from agent_config_loader import AgentConfig, ConfigLoadError, field

schema = {
    "model":       field(str,   "claude-3-opus", description="LLM model name"),
    "max_tokens":  field(int,   1024),
    "temperature": field(float, 0.7),
    "verbose":     field(bool,  False),
    "api_key":     field(str,   description="Anthropic API key (required)"),
}

try:
    cfg = AgentConfig.from_env(schema, prefix="MYAPP_")
except ConfigLoadError as e:
    print("Missing:", e.missing)
    print("Bad types:", e.bad_types)
    raise SystemExit(1)

print(cfg["model"])        # str
print(cfg["max_tokens"])   # int
print(cfg["verbose"])      # bool
```

Set env vars like `MYAPP_API_KEY=sk-...`, `MYAPP_MAX_TOKENS=2048`, etc.

## API

### `field(type=str, default=<required>, *, description="")`

Declare a config field. Omit `default` to make it required.

```python
field(str)              # required string
field(int, 1024)        # optional int, default 1024
field(bool, False)      # optional bool
field(str, description="API key")  # required with docs
```

### `AgentConfig.from_env(schema, *, prefix="", env=None)`

Load values from environment variables. Env var name = `prefix + field_name.upper()`.

Raises `ConfigLoadError` (subclass of `ValueError`) listing all missing required fields and coercion failures at once.

Pass `env={"KEY": "val"}` to test without touching `os.environ`.

### Value access

```python
cfg["model"]            # raises KeyError if absent
cfg.get("model")        # returns None if absent
"model" in cfg          # bool
cfg.keys()              # list in schema order
cfg.to_dict()           # shallow copy of all values
cfg.help()              # human-readable field summary
cfg.schema_for("model") # ConfigField descriptor
```

### Boolean coercion

`"1"`, `"true"`, `"yes"`, `"on"` (case-insensitive) → `True`. Everything else → `False`.

## License

MIT

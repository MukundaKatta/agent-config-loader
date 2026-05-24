"""Load and validate AI agent configuration from environment variables.

Define a schema with :func:`field` descriptors, then call
:meth:`AgentConfig.from_env` to populate values from ``os.environ``.
Missing required fields raise :exc:`ConfigLoadError`; string values are
auto-coerced to the declared type (``int``, ``float``, ``bool``).
"""

from __future__ import annotations

import os
from typing import Any

# Sentinel for required fields (no default)
_REQUIRED = object()


class ConfigLoadError(ValueError):
    """Raised when required config fields are missing or a value cannot be coerced.

    Attributes:
        missing: Field names that were required but not found.
        bad_types: Mapping of field name → raw string value for coercion failures.
    """

    def __init__(
        self,
        missing: list[str] | None = None,
        bad_types: dict[str, str] | None = None,
    ) -> None:
        self.missing = list(missing) if missing else []
        self.bad_types = dict(bad_types) if bad_types else {}
        parts: list[str] = []
        if self.missing:
            parts.append(f"Missing required fields: {self.missing}")
        if self.bad_types:
            parts.append(f"Type coercion failed: {self.bad_types}")
        super().__init__("; ".join(parts) or "Config load error.")


class ConfigField:
    """Descriptor for a single config field.

    Attributes:
        type: The Python type to coerce raw string values into.
        default: The default value, or ``_REQUIRED`` sentinel if the field is
            required.
        description: Human-readable description (shown in :meth:`AgentConfig.help`).
        required: ``True`` when no default has been set.
    """

    def __init__(
        self,
        type: type = str,  # noqa: A002
        default: Any = _REQUIRED,
        description: str = "",
    ) -> None:
        self.type = type
        self.default = default
        self.description = description

    @property
    def required(self) -> bool:
        """``True`` when no default was provided."""
        return self.default is _REQUIRED

    def coerce(self, raw: str) -> Any:
        """Coerce *raw* string to ``self.type``.

        Boolean coercion treats ``"1"``, ``"true"``, ``"yes"``, ``"on"``
        (case-insensitive) as ``True``; all other strings as ``False``.
        """
        if self.type is bool:
            return raw.strip().lower() in {"1", "true", "yes", "on"}
        return self.type(raw)

    def __repr__(self) -> str:
        req = "required" if self.required else f"default={self.default!r}"
        return f"ConfigField(type={self.type.__name__}, {req})"


def field(
    type: type = str,  # noqa: A002
    default: Any = _REQUIRED,
    *,
    description: str = "",
) -> ConfigField:
    """Shorthand for :class:`ConfigField`.

    Args:
        type: Python type for coercion (``str``, ``int``, ``float``, ``bool``).
        default: Default value, or omit to make the field required.
        description: Human-readable documentation string.

    Returns:
        A :class:`ConfigField` instance.

    Example::

        schema = {
            "model": field(str, "claude-3-opus", description="Model name"),
            "max_tokens": field(int, 1024, description="Max output tokens"),
            "verbose": field(bool, False, description="Enable verbose logging"),
            "api_key": field(str, description="Anthropic API key (required)"),
        }
    """
    return ConfigField(type=type, default=default, description=description)


class AgentConfig:
    """Validated agent configuration loaded from environment variables.

    Args:
        values: Mapping of field name → coerced value.
        schema: The :class:`ConfigField` schema used to build this config.

    Use :meth:`from_env` to construct an instance.

    Example::

        schema = {
            "model": field(str, "claude-3-opus"),
            "max_tokens": field(int, 1024),
            "api_key": field(str),
        }
        cfg = AgentConfig.from_env(schema, prefix="MYAPP_")
        cfg["model"]            # "claude-3-opus" or env override
        cfg["max_tokens"]       # int
        cfg.get("api_key")      # str or None
    """

    def __init__(
        self,
        values: dict[str, Any],
        schema: dict[str, ConfigField],
    ) -> None:
        self._values = dict(values)
        self._schema = dict(schema)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_env(
        cls,
        schema: dict[str, ConfigField],
        *,
        prefix: str = "",
        env: dict[str, str] | None = None,
    ) -> AgentConfig:
        """Load config values from environment variables.

        For each field in *schema*, look up ``prefix + field_name.upper()``
        in the environment.  Missing required fields and coercion failures
        accumulate and are raised together as a single :exc:`ConfigLoadError`.

        Args:
            schema: Mapping of field name → :class:`ConfigField`.
            prefix: Optional uppercase prefix prepended to env var names.
            env: Optional environment dict (defaults to ``os.environ``).

        Returns:
            A new :class:`AgentConfig`.

        Raises:
            ConfigLoadError: On missing required fields or type coercion failure.
        """
        environment = env if env is not None else dict(os.environ)
        values: dict[str, Any] = {}
        missing: list[str] = []
        bad_types: dict[str, str] = {}

        for name, cfg_field in schema.items():
            env_key = prefix + name.upper()
            raw = environment.get(env_key)

            if raw is None:
                if cfg_field.required:
                    missing.append(name)
                else:
                    values[name] = cfg_field.default
            else:
                try:
                    values[name] = cfg_field.coerce(raw)
                except (ValueError, TypeError):
                    bad_types[name] = raw

        if missing or bad_types:
            raise ConfigLoadError(missing=missing, bad_types=bad_types)

        return cls(values=values, schema=schema)

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    def __getitem__(self, key: str) -> Any:
        if key not in self._values:
            raise KeyError(key)
        return self._values[key]

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for *key*, or *default* if not present."""
        return self._values.get(key, default)

    def __contains__(self, key: str) -> bool:
        return key in self._values

    def keys(self) -> list[str]:
        """Return field names in schema order."""
        return list(self._schema.keys())

    def to_dict(self) -> dict[str, Any]:
        """Return a shallow copy of all values."""
        return dict(self._values)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def schema_for(self, key: str) -> ConfigField:
        """Return the :class:`ConfigField` descriptor for *key*."""
        return self._schema[key]

    def help(self) -> str:
        """Return a human-readable summary of all fields."""
        lines: list[str] = []
        for name, cfg_field in self._schema.items():
            default = "required" if cfg_field.required else repr(cfg_field.default)
            desc = f"  — {cfg_field.description}" if cfg_field.description else ""
            lines.append(f"{name} ({cfg_field.type.__name__}, {default}){desc}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        keys = list(self._values.keys())
        return f"AgentConfig(fields={keys!r})"

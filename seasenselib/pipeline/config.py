"""
Configuration system for pipelines (stage-based).

This module provides configuration loading from files and dictionaries.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
import logging
from importlib import resources
import json
import math


logger = logging.getLogger(__name__)


class StageConfig:
    """
    Configuration for a single stage.

    Attributes
    ----------
    name : str
        The stage name (must match registry).
    enabled : bool
        Whether this stage is enabled.
    config : Dict[str, Any]
        Stage-specific configuration.
    """

    def __init__(
        self,
        name: str,
        enabled: bool = True,
        config: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.enabled = enabled
        self.config = config or {}

    def __repr__(self) -> str:
        return f"StageConfig(name='{self.name}', enabled={self.enabled})"


class PipelineConfig:
    """
    Configuration for a pipeline.

    Can be loaded from:
    - Dictionary
    - YAML file
    - TOML file
    - Built programmatically

    Examples
    --------
    >>> config = PipelineConfig()
    >>> config.add_stage('mapping')
    >>> config.add_stage('metadata_enrichment')
    >>>
    >>> # Or from dict
    >>> config = PipelineConfig.from_dict({
    ...     'stages': [
    ...         {'name': 'mapping'},
    ...         {'name': 'metadata_enrichment'},
    ...     ]
    ... })
    """

    def __init__(self):
        """Initialize empty pipeline configuration."""
        self.pipeline: List[StageConfig] = []
        self.global_config: Dict[str, Any] = {}

    def add_stage(
        self,
        name: str,
        enabled: bool = True,
        config: Optional[Dict[str, Any]] = None
    ) -> 'PipelineConfig':
        """
        Add a stage to the configuration.
        """
        stage_config = StageConfig(name, enabled, config)
        self.pipeline.append(stage_config)
        return self

    def remove_stage(self, name: str) -> 'PipelineConfig':
        """Remove a stage from configuration."""
        self.pipeline = [stage for stage in self.pipeline if stage.name != name]
        return self

    def disable_stage(self, name: str) -> 'PipelineConfig':
        """Disable a stage (keep in config but set enabled=False)."""
        for stage in self.pipeline:
            if stage.name == name:
                stage.enabled = False
        return self

    def enable_stage(self, name: str) -> 'PipelineConfig':
        """Enable a stage."""
        for stage in self.pipeline:
            if stage.name == name:
                stage.enabled = True
        return self

    def upsert_stage(
        self,
        name: str,
        enabled: Optional[bool] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> 'PipelineConfig':
        """
        Update an existing stage config or add a new one.
        """
        for stage in self.pipeline:
            if stage.name == name:
                if enabled is not None:
                    stage.enabled = enabled
                if config is not None:
                    stage.config.update(config)
                return self
        return self.add_stage(name, enabled=(enabled if enabled is not None else True), config=config)

    def get_enabled_stages(self) -> List[StageConfig]:
        """Get list of enabled stages."""
        return [stage for stage in self.pipeline if stage.enabled]

    def set_global_config(self, key: str, value: Any) -> 'PipelineConfig':
        """Set a global configuration value."""
        self.global_config[key] = value
        return self

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PipelineConfig':
        """
        Load configuration from dictionary.

        Structure:
        {
            'stages': [
                {'name': 'mapping', 'enabled': True, 'config': {...}},
                ...
            ],
            'global': {...}
        }
        """
        config = cls()

        stage_entries = data.get('stages', [])
        for stage_data in stage_entries:
            config.add_stage(
                name=stage_data['name'],
                enabled=stage_data.get('enabled', True),
                config=stage_data.get('config')
            )

        config.global_config = dict(data.get('global', {}))

        return config

    @classmethod
    def from_file(cls, filepath: Union[str, Path]) -> 'PipelineConfig':
        """Load configuration from YAML, TOML, or JSON file."""
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"Configuration file not found: {filepath}")

        if filepath.suffix in ['.yaml', '.yml']:
            return cls._from_yaml(filepath)
        if filepath.suffix == '.toml':
            return cls._from_toml(filepath)
        if filepath.suffix == '.json':
            return cls._from_json(filepath)
        raise ValueError(
            f"Unsupported configuration format: {filepath.suffix}. "
            "Use .yaml, .yml, .toml, or .json"
        )

    @classmethod
    def _from_yaml(cls, filepath: Path) -> 'PipelineConfig':
        try:
            import yaml
        except ImportError:
            raise ImportError(
                "PyYAML is required to load YAML configuration. "
                "Install with: pip install pyyaml"
            )

        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)

        return cls.from_dict(data)

    @classmethod
    def _from_toml(cls, filepath: Path) -> 'PipelineConfig':
        import sys

        if sys.version_info >= (3, 11):
            import tomllib
        else:
            try:
                import tomli as tomllib
            except ImportError:
                raise ImportError(
                    "tomli is required to load TOML configuration on Python < 3.11. "
                    "Install with: pip install tomli"
                )

        with open(filepath, 'rb') as f:
            data = tomllib.load(f)

        return cls.from_dict(data)

    @classmethod
    def _from_json(cls, filepath: Path) -> 'PipelineConfig':
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_resource(cls, name: str) -> 'PipelineConfig':
        """
        Load a built-in pipeline profile from package resources.

        Parameters
        ----------
        name : str
            Profile name (without extension). Example: 'default'
        """
        filename = f"{name}.json"
        try:
            with resources.files('seasenselib.config.pipeline').joinpath(filename).open('r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Profile not found: {name}") from e
        return cls.from_dict(data)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'stages': [
                {
                    'name': stage.name,
                    'enabled': stage.enabled,
                    'config': stage.config,
                }
                for stage in self.pipeline
            ],
            'global': self.global_config,
        }

    def __repr__(self) -> str:
        enabled = len(self.get_enabled_stages())
        return f"PipelineConfig(stages={len(self.pipeline)}, enabled={enabled})"


def apply_default_latitude(config: PipelineConfig, default_latitude: float) -> PipelineConfig:
    """Configure the derivation stage to use an explicit fallback latitude.

    The fallback is only valid for processing stages that explicitly opt into it.
    It must never be treated as metadata from the instrument or input file.
    """
    try:
        latitude = float(default_latitude)
    except (TypeError, ValueError) as exc:
        raise ValueError("default_latitude must be a numeric latitude in degrees north") from exc

    if not math.isfinite(latitude) or latitude < -90.0 or latitude > 90.0:
        raise ValueError("default_latitude must be between -90 and 90 degrees")

    derivation_stage = None
    for stage in config.pipeline:
        if stage.name == "derivation":
            derivation_stage = stage
            break

    if derivation_stage is None or not derivation_stage.enabled:
        raise ValueError("default_latitude requires an enabled derivation stage")

    depth_config = derivation_stage.config.get("depth", {})
    if depth_config is None:
        depth_config = {}
    if not isinstance(depth_config, dict):
        raise ValueError("derivation.depth config must be a mapping")

    updated_depth_config = dict(depth_config)
    updated_depth_config["use_default_latitude"] = True
    updated_depth_config["default_latitude"] = latitude
    derivation_stage.config["default_latitude"] = latitude
    derivation_stage.config["depth"] = updated_depth_config

    return config


def apply_default_longitude(config: PipelineConfig, default_longitude: float) -> PipelineConfig:
    """Configure the derivation stage to use an explicit fallback longitude."""
    try:
        longitude = float(default_longitude)
    except (TypeError, ValueError) as exc:
        raise ValueError("default_longitude must be a numeric longitude in degrees east") from exc

    if not math.isfinite(longitude) or longitude < -180.0 or longitude > 180.0:
        raise ValueError("default_longitude must be between -180 and 180 degrees")

    derivation_stage = None
    for stage in config.pipeline:
        if stage.name == "derivation":
            derivation_stage = stage
            break

    if derivation_stage is None or not derivation_stage.enabled:
        raise ValueError("default_longitude requires an enabled derivation stage")

    derivation_stage.config["default_longitude"] = longitude

    return config


__all__ = [
    "StageConfig",
    "PipelineConfig",
    "apply_default_latitude",
    "apply_default_longitude",
]

"""
Derivation stage.

Derives oceanographic parameters when inputs are available.
"""

from __future__ import annotations

from typing import Dict, Any, Optional, List

from ..base import Stage, StageContext
from .handlers.derivation_runner import DerivationRunner
from ..interfaces import IDerivation
from ..handler_registry import HandlerRegistry, HANDLER_GROUP_DERIVATIONS


class DerivationStage(Stage):
    """Stage 2: Parameter derivation."""

    def __init__(self, derivations: Optional[List[IDerivation]] = None):
        self._derivation = DerivationRunner(derivations=derivations)

    def name(self) -> str:
        return "derivation"

    def configure(self, config: Dict[str, Any]) -> None:
        unit_guard = bool(config.get('unit_guard', True))
        input_units = config.get('input_units')

        # Rebuild derivation list based on handler names, or patch existing
        # built-ins when only handler configuration is provided.
        from .handlers.density_derivation import DensityDerivation
        from .handlers.depth_derivation import DepthDerivation
        from .handlers.potential_temperature_derivation import PotentialTemperatureDerivation
        from .handlers.conservative_temperature_derivation import ConservativeTemperatureDerivation
        from .handlers.absolute_salinity_derivation import AbsoluteSalinityDerivation
        from .handlers.sound_speed_derivation import SoundSpeedDerivation

        depth_config = config.get('depth', {})
        if not isinstance(depth_config, dict):
            depth_config = {}
        has_depth_config = bool(depth_config)
        depth_defaults = {
            'use_default_latitude': False,
            'default_latitude': 45.0,
        }
        depth_defaults.update(depth_config)
        default_latitude = config.get('default_latitude')
        default_longitude = config.get('default_longitude')
        if default_latitude is not None and not has_depth_config:
            depth_defaults['use_default_latitude'] = True
            depth_defaults['default_latitude'] = default_latitude
            has_depth_config = True

        handlers = config.get('handlers')
        if not isinstance(handlers, list) or not handlers:
            derivations = self._derivation.derivations
            if has_depth_config:
                derivations = [
                    DepthDerivation(
                        use_default_latitude=bool(depth_defaults.get('use_default_latitude', False)),
                        default_latitude=depth_defaults.get('default_latitude', 45.0),
                    )
                    if isinstance(derivation, DepthDerivation)
                    else derivation
                    for derivation in derivations
                ]
            if default_latitude is not None or default_longitude is not None:
                derivations = [
                    ConservativeTemperatureDerivation(
                        default_latitude=default_latitude,
                        default_longitude=default_longitude,
                    )
                    if isinstance(derivation, ConservativeTemperatureDerivation)
                    else AbsoluteSalinityDerivation(
                        default_latitude=default_latitude,
                        default_longitude=default_longitude,
                    )
                    if isinstance(derivation, AbsoluteSalinityDerivation)
                    else derivation
                    for derivation in derivations
                ]
            self._derivation = DerivationRunner(
                derivations=derivations,
                unit_guard=unit_guard,
                input_units=input_units,
            )
            return

        mapping = {
            'density': DensityDerivation,
            'depth': DepthDerivation,
            'potential_temperature': PotentialTemperatureDerivation,
            'conservative_temperature': ConservativeTemperatureDerivation,
            'absolute_salinity': AbsoluteSalinityDerivation,
            'sound_speed': SoundSpeedDerivation,
        }
        if any(name not in mapping for name in handlers):
            plugin_mapping = HandlerRegistry.get(HANDLER_GROUP_DERIVATIONS, IDerivation)
            for name, cls in plugin_mapping.items():
                if name not in mapping:
                    mapping[name] = cls

        derivations: List[IDerivation] = []
        for name in handlers:
            if name == 'depth':
                derivations.append(DepthDerivation(
                    use_default_latitude=bool(depth_defaults.get('use_default_latitude', False)),
                    default_latitude=depth_defaults.get('default_latitude', 45.0),
                ))
                continue
            if name == 'conservative_temperature':
                derivations.append(ConservativeTemperatureDerivation(
                    default_latitude=default_latitude,
                    default_longitude=default_longitude,
                ))
                continue
            if name == 'absolute_salinity':
                derivations.append(AbsoluteSalinityDerivation(
                    default_latitude=default_latitude,
                    default_longitude=default_longitude,
                ))
                continue
            cls = mapping.get(name)
            if cls is not None:
                try:
                    derivations.append(cls())
                except Exception:
                    continue

        if derivations:
            self._derivation = DerivationRunner(
                derivations=derivations,
                unit_guard=unit_guard,
                input_units=input_units,
            )

    def process(self, context: StageContext) -> StageContext:
        return self._derivation.process(context)

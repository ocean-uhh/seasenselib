"""
Unit handling stage.

Validates, normalizes, and optionally converts units.
"""

from __future__ import annotations

from typing import Dict, Any

from ..base import Stage, StageContext
from .handlers.unit_normalizer import UnitNormalizer
from .handlers.unit_converter import UnitConverter
from .handlers.conductivity_normalizer import ConductivityNormalizer


class UnitHandlingStage(Stage):
    """Stage 4: Unit handling and normalization."""

    def __init__(self):
        self._normalizer = UnitNormalizer()
        self._converter = UnitConverter()
        self._cond_normalizer = ConductivityNormalizer()

    def name(self) -> str:
        return "unit_handling"

    def configure(self, config: Dict[str, Any]) -> None:
        handlers = config.get('handlers')
        if isinstance(handlers, list) and handlers:
            self._enable_normalize = 'normalize' in handlers
            self._enable_convert = 'convert' in handlers
            self._enable_cond_normalize = 'conductivity_normalize' in handlers
        else:
            self._enable_normalize = True
            self._enable_convert = False
            self._enable_cond_normalize = True

        # Pass config through to normalizer / converter
        normalizer_cfg = dict(config)
        normalizer_cfg.pop('handlers', None)
        self._normalizer = UnitNormalizer(
            strict=normalizer_cfg.get('strict', False),
            auto_convert=normalizer_cfg.get('auto_convert', True),
            custom_conversions=normalizer_cfg.get('custom_conversions'),
            expected_units=normalizer_cfg.get('expected_units'),
        )
        self._converter = UnitConverter(
            use_pint=bool(normalizer_cfg.get('use_pint', True)),
            expected_units=normalizer_cfg.get('expected_units'),
            conversion_mode=normalizer_cfg.get('conversion_mode', 'duplicate_keep_original'),
            original_suffix=normalizer_cfg.get('original_suffix', '_original'),
        )

    def process(self, context: StageContext) -> StageContext:
        ds = context.dataset
        from ..utils import record_handler_applied

        if getattr(self, '_enable_normalize', True):
            ds, issues, relabels = self._normalizer.normalize(ds)
            if issues:
                context.metadata['unit_validation_issues'] = issues
            if relabels:
                context.metadata.setdefault('unit_conversions', []).extend(relabels)
            record_handler_applied(context.metadata, self.name(), "normalize")

        if getattr(self, '_enable_cond_normalize', True):
            ds, cond_normalizations = self._cond_normalizer.normalize(ds)
            if cond_normalizations:
                context.metadata.setdefault('unit_conversions', []).extend(cond_normalizations)
            record_handler_applied(context.metadata, self.name(), "conductivity_normalize")

        if getattr(self, '_enable_convert', False):
            ds, conversions = self._converter.convert(ds)
            if conversions:
                context.metadata.setdefault('unit_conversions', []).extend(conversions)
            record_handler_applied(context.metadata, self.name(), "convert")

        context.dataset = ds
        return context

"""
Mapping stage.

Orchestrates variable name mapping strategies into the canonical data model.
"""

from __future__ import annotations

from typing import Dict, Any

from ..base import Stage, StageContext
from .handlers.mapping_runner import MappingRunner
from ..handler_registry import HandlerRegistry, HANDLER_GROUP_MAPPING
from ..interfaces import IMappingStrategy


class MappingStage(Stage):
    """Stage 1: Variable mapping."""

    def __init__(self):
        self._mapping = MappingRunner()
        self._handler_order: list[str] = []

    def name(self) -> str:
        return "mapping"

    def configure(self, config: Dict[str, Any]) -> None:
        handlers = config.get('handlers')
        plugin_strategies = []
        handler_order: list[str] = []
        using_handler_list = False
        if handlers is None:
            handlers = config.get('strategies')
        if isinstance(handlers, list) and handlers:
            config = dict(config)
            config['use_custom_mappings'] = 'user_mapping' in handlers or 'user_config_mapping' in handlers
            config['use_reader_mappings'] = 'format_specific' in handlers or 'reader_mapping' in handlers
            config['use_default_mappings'] = 'default_mapping' in handlers
            config['use_regex'] = 'regex_mapping' in handlers
            builtin_names = {
                'user_mapping', 'user_config_mapping', 'format_specific',
                'reader_mapping', 'default_mapping', 'regex_mapping'
            }
            if any(name not in builtin_names for name in handlers):
                plugin_map = HandlerRegistry.get(HANDLER_GROUP_MAPPING, IMappingStrategy)
                for name in handlers:
                    if name in plugin_map and name not in builtin_names:
                        try:
                            plugin_strategies.append(plugin_map[name]())
                        except Exception:
                            continue
            if plugin_strategies:
                config['plugin_strategies'] = plugin_strategies
            handler_order = list(handlers)
            using_handler_list = True
        else:
            handler_order = []
            if config.get('use_custom_mappings', True):
                handler_order.append('user_mapping')
            if config.get('use_reader_mappings', True):
                handler_order.append('format_specific')
            if config.get('use_default_mappings', True):
                handler_order.append('default_mapping')
            if config.get('use_regex', True):
                handler_order.append('regex_mapping')

        custom_mappings = config.get('custom_mappings') or {}
        reader_mappings = config.get('reader_mappings') or {}
        filtered_order: list[str] = []
        for name in handler_order:
            if name in ('user_mapping', 'user_config_mapping') and not custom_mappings:
                continue
            if name in ('format_specific', 'reader_mapping') and not reader_mappings:
                continue
            filtered_order.append(name)
        if plugin_strategies and not using_handler_list:
            for strategy in plugin_strategies:
                filtered_order.append(f"plugin:{strategy.__class__.__name__}")
        self._handler_order = filtered_order
        self._mapping.configure(config)

    def process(self, context: StageContext) -> StageContext:
        from ..utils import record_handler_applied
        for name in self._handler_order:
            record_handler_applied(context.metadata, self.name(), name)
        return self._mapping.process(context)

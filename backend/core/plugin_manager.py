import os
import importlib
import inspect
import pkgutil
import logging
from typing import List, Dict, Type
from backend.services.normalization.adapters.base import BaseEngineAdapter

logger = logging.getLogger(__name__)

class PluginManager:
    def __init__(self, plugin_dir: str = "plugins"):
        self.plugin_dir = plugin_dir
        self.adapters: Dict[str, Type[BaseEngineAdapter]] = {}

    def discover_plugins(self) -> None:
        if not os.path.exists(self.plugin_dir):
            os.makedirs(self.plugin_dir, exist_ok=True)
            return

        for _, name, _ in pkgutil.iter_modules([self.plugin_dir]):
            try:
                module = importlib.import_module(f"{self.plugin_dir}.{name}")
                for item_name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, BaseEngineAdapter) and obj is not BaseEngineAdapter:
                        plugin_id = getattr(obj, "plugin_id", name)
                        self.adapters[plugin_id] = obj
                        logger.info(f"Loaded plugin: {plugin_id} ({item_name})")
            except Exception as e:
                logger.error(f"Failed to load plugin {name}: {e}")

    def get_adapter(self, plugin_id: str) -> Type[BaseEngineAdapter]:
        if plugin_id not in self.adapters:
            raise ValueError(f"Plugin {plugin_id} not found")
        return self.adapters[plugin_id]

plugin_manager = PluginManager()
plugin_manager.discover_plugins()

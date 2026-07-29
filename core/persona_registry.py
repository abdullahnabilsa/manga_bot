# File: core/persona_registry.py
from __future__ import annotations

import importlib
import inspect
import logging
import os
import sys
from typing import Dict, List

# --- إصلاح خطأ مسار الاستيراد في بيئات السيرفر ---
# نحصل على المسار الجذري للمشروع (مجلد واحد قبل مجلد core)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
# ----------------------------------------------

from modules.base_persona import BasePersona

logger = logging.getLogger(__name__)

class PersonaRegistry:
    """
    Dynamic Discovery Engine for Persona Plugins.
    Scans the 'modules/' directory and automatically loads any valid persona.
    """
    
    def __init__(self, modules_dir: str = "modules") -> None:
        self._handlers: Dict[str, BasePersona] = {}
        # تحويل المسار النسبي إلى مطلق بناءً على جذر المشروع
        self._modules_dir = os.path.join(PROJECT_ROOT, modules_dir)
        self._discover_personas()

    def _discover_personas(self) -> None:
        if not os.path.isdir(self._modules_dir):
            logger.error(f"Modules directory not found: {self._modules_dir}")
            return

        for module_name in os.listdir(self._modules_dir):
            module_path = os.path.join(self._modules_dir, module_name)
            if os.path.isdir(module_path) and not module_name.startswith('_'):
                try:
                    # محاولة استيراد ملف persona.py من داخل مجلد الوحدة
                    full_module_name = f"modules.{module_name}.persona"
                    module = importlib.import_module(full_module_name)
                    
                    # البحث عن الكلاسات التي ترث من BasePersona
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, BasePersona) and obj is not BasePersona:
                            instance = obj()
                            self._handlers[instance.name.lower()] = instance
                            logger.info(f"Successfully loaded persona plugin: {instance.name}")
                except Exception as e:
                    logger.error(f"Failed to load persona from {module_name}: {e}", exc_info=True)

        if "default translator" not in self._handlers:
            logger.critical("Default Translator persona failed to load! Fallback mechanism disabled.")

    def get_handler(self, persona_name: str) -> BasePersona:
        """Returns the appropriate handler for a given persona name (case-insensitive)."""
        if not persona_name:
            return self._handlers.get("default translator")
            
        for key, handler in self._handlers.items():
            if key == persona_name.lower():
                return handler
                
        return self._handlers.get("default translator")

    def get_available_personas(self) -> List[str]:
        """Returns list of available persona display names."""
        return [p.name for p in self._handlers.values()]
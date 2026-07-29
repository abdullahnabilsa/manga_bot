# File: utils/regex_template_engine.py
from __future__ import annotations

import re
from typing import Any

class RegexTemplateEngine:
    """
    A lightweight Regex-based template engine.
    Supports {{variable}} replacement and {{#if variable}}...{{/if}} conditional blocks.
    """
    
    # Matches {{#if variable}} content {{/if}} (non-greedy, includes newlines)
    _IF_PATTERN = re.compile(r"\{\{#if (\w+)\}\}(.*?)\{\{/if\}\}", re.DOTALL)
    # Matches {{variable}}
    _VAR_PATTERN = re.compile(r"\{\{(\w+)\}\}")

    def __init__(self, template: str) -> None:
        self.template = template

    def render(self, context: Any) -> str:
        text = self.template
        
        # 1. Process conditional blocks first
        def replace_conditional(match: re.Match) -> str:
            var_name = match.group(1)
            content = match.group(2)
            
            # Handle both dict and Pydantic model/object
            if isinstance(context, dict):
                val = context.get(var_name)
            else:
                val = getattr(context, var_name, None)
                
            # If value exists and is not empty, return the inner content
            # Otherwise, return empty string (removes the block)
            if val:
                return content.strip()
            return ""
            
        text = self._IF_PATTERN.sub(replace_conditional, text)
        
        # 2. Process variable replacement
        def replace_variable(match: re.Match) -> str:
            var_name = match.group(1)
            if isinstance(context, dict):
                val = context.get(var_name, "")
            else:
                val = getattr(context, var_name, "")
            return str(val) if val is not None else ""
            
        text = self._VAR_PATTERN.sub(replace_variable, text)
        
        # 3. Clean up excessive newlines caused by removed blocks
        text = re.sub(r"\n{3,}", "\n\n", text)
        
        return text.strip()
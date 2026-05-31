from __future__ import annotations

import dataclasses
import logging
import sys
import types
from pathlib import Path
from typing import Generic, TypeVar

# --- Plugin path setup ---
_plugin_parent = str(Path(__file__).resolve().parent.parent.parent)
if _plugin_parent not in sys.path:
    sys.path.insert(0, _plugin_parent)

# --- Mock astrbot framework modules ---
# This plugin depends on the astrbot framework, but unit tests should run
# without it. We register minimal mock modules in sys.modules so that
# `from astrbot.xxx import ...` succeeds in the plugin source files.

T = TypeVar("T")


# ---- Minimal stand-ins for real astrbot classes ----


@dataclasses.dataclass
class _MockFunctionTool(Generic[T]):
    """Stand-in for astrbot.core.agent.tool.FunctionTool.

    Provides the same field layout so that @dataclass subclasses
    (CharacterTool, etc.) work correctly under test.
    """

    name: str = ""
    description: str = ""
    parameters: dict = dataclasses.field(default_factory=dict)

    async def call(self, context, **kwargs):
        raise NotImplementedError


class _MockStar:
    """Stand-in for astrbot.api.star.Star base class."""

    def __init__(self, context=None):
        self.context = context

    async def terminate(self):
        pass


# ---- Decorator helpers so @filter.command_group / @group.command work ----


def _identity(func):
    """Decorator that returns the function unchanged."""
    return func


class _CommandGroupMock:
    def command(self, cmd_name):
        return _identity


class _FilterMock:
    def command_group(self, name):
        def decorator(func):
            func.command = _CommandGroupMock().command
            return func

        return decorator


# ---- Module factory ----


def _make_module(name, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    return mod


# ---- Register all mocks ----


def _setup_astrbot_mocks():
    """Populate sys.modules with lightweight mocks (only if not already present)."""

    # Top-level astrbot
    sys.modules.setdefault("astrbot", _make_module("astrbot"))

    # astrbot.api — needs a real logger so storage.py can call logger.error(...)
    sys.modules.setdefault(
        "astrbot.api",
        _make_module("astrbot.api", logger=logging.getLogger("astrbot"), AstrBotConfig=type("AstrBotConfig", (), {})),
    )

    # astrbot.api.event
    sys.modules.setdefault(
        "astrbot.api.event",
        _make_module("astrbot.api.event", filter=_FilterMock(), AstrMessageEvent=type("AstrMessageEvent", (), {})),
    )

    # astrbot.api.star
    sys.modules.setdefault(
        "astrbot.api.star",
        _make_module("astrbot.api.star", Star=_MockStar, Context=type("Context", (), {})),
    )

    # astrbot.api.message_components
    sys.modules.setdefault(
        "astrbot.api.message_components",
        _make_module("astrbot.api.message_components"),
    )

    # Intermediate packages
    sys.modules.setdefault("astrbot.core", _make_module("astrbot.core"))
    sys.modules.setdefault("astrbot.core.agent", _make_module("astrbot.core.agent"))

    # astrbot.core.agent.tool — needs the real FunctionTool dataclass
    sys.modules.setdefault(
        "astrbot.core.agent.tool",
        _make_module(
            "astrbot.core.agent.tool",
            FunctionTool=_MockFunctionTool,
            ToolExecResult=str,
            ToolSet=list,
        ),
    )

    # astrbot.core.agent.run_context
    sys.modules.setdefault(
        "astrbot.core.agent.run_context",
        _make_module("astrbot.core.agent.run_context", ContextWrapper=type("ContextWrapper", (), {})),
    )

    # astrbot.core.astr_agent_context
    sys.modules.setdefault(
        "astrbot.core.astr_agent_context",
        _make_module("astrbot.core.astr_agent_context", AstrAgentContext=type("AstrAgentContext", (), {})),
    )

    # astrbot.core.utils (intermediate)
    sys.modules.setdefault("astrbot.core.utils", _make_module("astrbot.core.utils"))

    # astrbot.core.utils.astrbot_path
    sys.modules.setdefault(
        "astrbot.core.utils.astrbot_path",
        _make_module(
            "astrbot.core.utils.astrbot_path",
            get_astrbot_data_path=lambda: "/tmp/test_astrbot_data",
        ),
    )

    # Mock quart if not installed (used by main.py for Web API)
    try:
        import quart  # noqa: F401
    except ImportError:
        from unittest.mock import MagicMock as _MMC
        _quart_mock = _make_module(
            "quart",
            jsonify=lambda *a, **kw: {},
            request=_MMC(),
        )
        sys.modules.setdefault("quart", _quart_mock)


_setup_astrbot_mocks()

# --- Event loop policy for Python 3.12+ ---
# Python 3.12 removed implicit event loop creation in get_event_loop().
# The `novel` fixture in test_tools.py uses get_event_loop().run_until_complete()
# which fails without an existing loop. Install a policy that auto-creates one.
import asyncio


class _AutoCreateEventLoopPolicy(asyncio.DefaultEventLoopPolicy):
    def get_event_loop(self):
        try:
            return super().get_event_loop()
        except RuntimeError:
            loop = self.new_event_loop()
            self.set_event_loop(loop)
            return loop


asyncio.set_event_loop_policy(_AutoCreateEventLoopPolicy())

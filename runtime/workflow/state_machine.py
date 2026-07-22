"""工作流状态机（预留接口）。"""
from __future__ import annotations
from enum import Enum
from typing import Any


class WorkflowState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class StateMachine:
    """工作流状态机（预留接口）。
    TODO: 后续实现复杂工作流的状态管理
    """
    pass

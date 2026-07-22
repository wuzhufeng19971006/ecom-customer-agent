"""任务规划器：将复杂请求分解为子任务。

当前为预留接口，客服场景大多数走 RAG + 工具调用，不需要复杂规划。
后续若需要多步骤任务（如"先查订单再查物流再申请退款"），再填充实现。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TaskStep:
    """单个执行步骤。"""
    step_id: str
    action: str  # "rag" | "tool_call" | "ask_user"
    description: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)


@dataclass
class TaskPlan:
    """任务计划。"""
    plan_id: str
    steps: list[TaskStep] = field(default_factory=list)
    is_linear: bool = True  # 是否线性执行


class TaskPlanner:
    """任务规划器（预留接口）。"""

    async def plan(self, user_request: str, *, context: dict[str, Any] | None = None) -> TaskPlan:
        """生成执行计划。

        TODO: 后续接入 LLM 做任务分解
        当前默认返回单步 RAG 计划
        """
        from uuid import uuid4
        return TaskPlan(
            plan_id=f"plan-{uuid4().hex[:8]}",
            steps=[TaskStep(
                step_id="s1",
                action="rag",
                description=f"检索并回答: {user_request[:80]}",
            )],
            is_linear=True,
        )

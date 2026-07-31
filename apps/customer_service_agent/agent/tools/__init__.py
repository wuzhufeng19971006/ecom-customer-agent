"""客服 Agent 工具集合。

工具通过 OpenAI function-calling 暴露给 LLM。
一期工具：query_order / query_logistics / query_product / handoff_human
"""

from __future__ import annotations

from apps.customer_service_agent.adapters.base import PlatformAdapter
from runtime.llm.llm_provider import ToolSpec
from tool_center.manager.tool_executor import ToolExecutor

# ===== 工具规格（暴露给 LLM） =====

QUERY_ORDER = ToolSpec(
    name="query_order",
    description="根据订单号查询订单状态、金额、商品。",
    parameters={
        "type": "object",
        "properties": {
            "order_id": {"type": "string", "description": "抖店订单号"},
        },
        "required": ["order_id"],
    },
)

QUERY_LOGISTICS = ToolSpec(
    name="query_logistics",
    description="根据订单号查询物流轨迹。",
    parameters={
        "type": "object",
        "properties": {
            "order_id": {"type": "string", "description": "抖店订单号"},
        },
        "required": ["order_id"],
    },
)

QUERY_PRODUCT = ToolSpec(
    name="query_product",
    description="根据 SKU ID 查询商品库存与属性。",
    parameters={
        "type": "object",
        "properties": {
            "sku_id": {"type": "string", "description": "抖店商品 ID"},
        },
        "required": ["sku_id"],
    },
)

HANDOFF_HUMAN = ToolSpec(
    name="handoff_human",
    description="当无法处理、用户强烈要求、或涉及金额纠纷时，转人工。",
    parameters={
        "type": "object",
        "properties": {
            "reason": {"type": "string", "description": "转人工原因"},
        },
        "required": ["reason"],
    },
)

ALL_TOOLS = [QUERY_ORDER, QUERY_LOGISTICS, QUERY_PRODUCT, HANDOFF_HUMAN]


async def _query_order_handler(adapter: PlatformAdapter, order_id: str) -> str:
    order = await adapter.query_order(order_id)
    return str(order.__dict__) if order else "未找到该订单"


async def _query_logistics_handler(adapter: PlatformAdapter, order_id: str) -> str:
    info = await adapter.query_logistics(order_id)
    return str(info.__dict__) if info else "未找到物流信息"


async def _query_product_handler(adapter: PlatformAdapter, sku_id: str) -> str:
    prod = await adapter.query_product(sku_id)
    return str(prod.__dict__) if prod else "未找到商品"


async def _handoff_human_handler(reason: str = "未指定") -> str:
    return f"已发起转人工，原因：{reason}"


async def execute_tool(
    name: str,
    args: dict,
    *,
    adapter: PlatformAdapter,
) -> str:
    """执行工具，返回给 LLM 的字符串结果。

    保留向后兼容：旧代码仍可直接调用此函数。
    新代码应优先使用 create_tool_executor() + ToolExecutor.execute()。
    """
    if name == "query_order":
        return await _query_order_handler(adapter, **args)
    if name == "query_logistics":
        return await _query_logistics_handler(adapter, **args)
    if name == "query_product":
        return await _query_product_handler(adapter, **args)
    if name == "handoff_human":
        return await _handoff_human_handler(**args)
    return f"unknown tool: {name}"


def create_tool_executor(adapter: PlatformAdapter) -> ToolExecutor:
    """创建已注册所有 handler 的 ToolExecutor 实例。

    handler 通过闭包绑定 adapter，调用时只需传 arguments。
    """
    executor = ToolExecutor()
    executor.register_handler(
        "query_order",
        lambda **kw: _query_order_handler(adapter, **kw),
    )
    executor.register_handler(
        "query_logistics",
        lambda **kw: _query_logistics_handler(adapter, **kw),
    )
    executor.register_handler(
        "query_product",
        lambda **kw: _query_product_handler(adapter, **kw),
    )
    executor.register_handler(
        "handoff_human",
        lambda **kw: _handoff_human_handler(**kw),
    )
    return executor

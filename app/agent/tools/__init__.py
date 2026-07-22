"""客服 Agent 工具集合。

工具通过 OpenAI function-calling 暴露给 LLM。
一期工具：query_order / query_logistics / query_product / handoff_human
"""

from __future__ import annotations

from app.adapters.base import PlatformAdapter
from app.llm.base import ToolSpec

# ===== 工具规格（暴露给 LLM） =====

QUERY_ORDER = ToolSpec(
    name="query_order",
    description="根据订单号查询订单状态、金额、商品。",
    parameters={
        "type": "object",
        "properties": {
            "order_id": {"type": "string", "description": "淘宝订单号"},
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
            "order_id": {"type": "string", "description": "淘宝订单号"},
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
            "sku_id": {"type": "string", "description": "淘宝商品 SKU ID"},
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


async def execute_tool(
    name: str,
    args: dict,
    *,
    adapter: PlatformAdapter,
) -> str:
    """执行工具，返回给 LLM 的字符串结果。"""
    if name == "query_order":
        order = await adapter.query_order(args["order_id"])
        return str(order.__dict__) if order else "未找到该订单"
    if name == "query_logistics":
        info = await adapter.query_logistics(args["order_id"])
        return str(info.__dict__) if info else "未找到物流信息"
    if name == "query_product":
        prod = await adapter.query_product(args["sku_id"])
        return str(prod.__dict__) if prod else "未找到商品"
    if name == "handoff_human":
        return f"已发起转人工，原因：{args.get('reason', '未指定')}"
    return f"unknown tool: {name}"

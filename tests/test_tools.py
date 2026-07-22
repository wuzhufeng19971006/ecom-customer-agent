"""工具注册中心与执行器测试。"""

import pytest

from tool_center.manager.tool_executor import ToolExecutor, ToolExecutionResult
from tool_center.registry.tool_registry import ToolRegistry, get_default_registry
from runtime.llm.llm_provider import ToolSpec


def _make_spec(name: str = "echo", desc: str = "echo tool") -> ToolSpec:
    return ToolSpec(
        name=name,
        description=desc,
        parameters={
            "type": "object",
            "properties": {"msg": {"type": "string", "description": "消息"}},
            "required": ["msg"],
        },
    )


# ===== ToolRegistry 测试 =====


def test_tool_registry_register():
    reg = ToolRegistry()
    spec = _make_spec("echo", "回显工具")

    reg.register(spec)

    assert len(reg.list_all()) == 1
    assert reg.list_names() == ["echo"]
    assert reg.list_all()[0] is spec


def test_tool_registry_get():
    reg = ToolRegistry()
    spec = _make_spec("echo")
    reg.register(spec)

    assert reg.get("echo") is spec
    assert reg.get("not_exist") is None


def test_tool_registry_to_openai_format():
    reg = ToolRegistry()
    reg.register(_make_spec("echo", "回显工具"))
    reg.register(_make_spec("ping", "ping 工具"))

    fmt = reg.to_openai_format()

    assert len(fmt) == 2
    for item in fmt:
        assert item["type"] == "function"
        assert "name" in item["function"]
        assert "description" in item["function"]
        assert "parameters" in item["function"]
    names = {item["function"]["name"] for item in fmt}
    assert names == {"echo", "ping"}
    # 验证字段映射正确
    echo = next(item for item in fmt if item["function"]["name"] == "echo")
    assert echo["function"]["description"] == "回显工具"
    assert echo["function"]["parameters"]["type"] == "object"


def test_registry_register_duplicate_raises():
    reg = ToolRegistry()
    reg.register(_make_spec("echo"))
    with pytest.raises(ValueError, match="tool already registered"):
        reg.register(_make_spec("echo"))


def test_default_registry_has_tools():
    reg = get_default_registry()

    names = set(reg.list_names())
    assert names == {"query_order", "query_logistics", "query_product", "handoff_human"}
    # OpenAI 格式输出数量一致
    assert len(reg.to_openai_format()) == 4


# ===== ToolExecutor 测试 =====


async def test_executor_no_handler():
    executor = ToolExecutor(registry=ToolRegistry())

    result = await executor.execute("unknown_tool", {"x": 1})

    assert isinstance(result, ToolExecutionResult)
    assert result.success is False
    assert result.tool_name == "unknown_tool"
    assert "no handler registered" in result.error


async def test_executor_with_handler():
    executor = ToolExecutor(registry=ToolRegistry())

    async def echo_handler(msg: str) -> str:
        return f"echo:{msg}"

    executor.register_handler("echo", echo_handler)

    result = await executor.execute("echo", {"msg": "hello"})

    assert result.success is True
    assert result.tool_name == "echo"
    assert result.output == "echo:hello"
    assert result.raw == "echo:hello"


async def test_executor_tool_call_exception():
    """handler 抛异常时返回失败结果。"""
    executor = ToolExecutor(registry=ToolRegistry())

    async def boom(**kwargs):
        raise RuntimeError("boom")

    executor.register_handler("boom", boom)

    result = await executor.execute("boom", {})

    assert result.success is False
    assert result.error == "boom"


async def test_executor_execute_tool_calls_batch():
    """批量执行 LLM tool_calls（含 JSON 字符串参数）。"""
    executor = ToolExecutor(registry=ToolRegistry())

    async def add(a: int, b: int) -> str:
        return str(a + b)

    async def upper(text: str) -> str:
        return text.upper()

    executor.register_handler("add", add)
    executor.register_handler("upper", upper)

    tool_calls = [
        {"function": {"name": "add", "arguments": {"a": 1, "b": 2}}},
        {"function": {"name": "upper", "arguments": '{"text": "hi"}'}},  # JSON 字符串
        {"function": {"name": "nope", "arguments": {}}},  # 未注册
    ]

    results = await executor.execute_tool_calls(tool_calls)

    assert len(results) == 3
    assert results[0].success is True and results[0].output == "3"
    assert results[1].success is True and results[1].output == "HI"
    assert results[2].success is False

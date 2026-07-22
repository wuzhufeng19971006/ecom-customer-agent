"""自定义异常类。"""
from __future__ import annotations


class CustomerServiceError(Exception):
    """客服系统基础异常。"""


class ConfigError(CustomerServiceError):
    """配置错误。"""


class LLMProviderError(CustomerServiceError):
    """LLM Provider 调用错误。"""


class RetrievalError(CustomerServiceError):
    """检索错误。"""


class ToolExecutionError(CustomerServiceError):
    """工具执行错误。"""

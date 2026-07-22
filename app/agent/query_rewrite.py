"""兼容层：实际代码已迁移到 app.agent_runtime.conversation.context_builder

注意：QueryRewriteService 已改名为 ContextBuilder，这里通过别名保持向后兼容。
"""
from app.agent_runtime.conversation.context_builder import *  # noqa: F401, F403
from app.agent_runtime.conversation.context_builder import ContextBuilder as QueryRewriteService  # noqa: F401

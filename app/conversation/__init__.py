"""会话管理模块：管理多轮多模态上下文 + 事件驱动。

- state:    ConversationState 状态机
- event:    EventType 事件类型 + EventBus 异步事件总线
- decision: DecisionEngine 决策何时回答
- manager:  ConversationManager 编排整体流程
"""

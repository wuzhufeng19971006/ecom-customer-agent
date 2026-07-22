"""RBAC 角色权限控制（预留接口）。

电商客服场景的权限模型：
- customer:  仅能查询自己的订单/物流
- agent:     客服坐席，可查看订单、回复用户、转人工
- admin:     管理员，可配置知识库、查看审计日志

当前一期未启用权限校验，预留接口。
"""
from __future__ import annotations
from enum import Enum
from typing import Any


class Role(str, Enum):
    CUSTOMER = "customer"
    AGENT = "agent"
    ADMIN = "admin"


# 权限矩阵
PERMISSIONS: dict[Role, set[str]] = {
    Role.CUSTOMER: {"qa:ask", "order:query_own"},
    Role.AGENT: {"qa:ask", "order:query", "order:update", "message:reply", "handoff:assign"},
    Role.ADMIN: {"qa:ask", "order:query", "order:update", "message:reply",
                 "handoff:assign", "kb:manage", "audit:read"},
}


class RBACManager:
    """RBAC 权限管理器（预留接口）。"""

    def has_permission(self, role: Role, permission: str) -> bool:
        return permission in PERMISSIONS.get(role, set())

    def check(self, role: Role, permission: str) -> None:
        """校验权限，不通过则抛异常。"""
        if not self.has_permission(role, permission):
            raise PermissionError(f"role {role.value} lacks permission {permission}")

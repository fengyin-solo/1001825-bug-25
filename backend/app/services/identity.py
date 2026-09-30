"""操作账号与身份解析：缺陷登记的写操作必须能识别出操作人。

身份通过请求头传递（X-Operator-Name / X-Operator-Role / X-Operator-Team），
前端在页面头部切换账号后随每次请求带上；后端只认在册账号，三项缺一或对不上都视为未识别。
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote

from fastapi import Header

# 在册账号：姓名、岗位、归属班组。管理岗位的归属范围即本班组；总部管理覆盖全部班组。
ACCOUNTS: list[dict[str, str]] = [
    {"name": "张三", "role": "登记员", "team": "一班"},
    {"name": "李四", "role": "登记员", "team": "二班"},
    {"name": "王五", "role": "管理", "team": "一班"},
    {"name": "赵六", "role": "管理", "team": "二班"},
    {"name": "平台管理员", "role": "管理", "team": "总部"},
]
MANAGER_ROLE = "管理"
HQ_TEAM = "总部"


@dataclass(frozen=True)
class Operator:
    name: str
    role: str
    team: str

    @property
    def is_manager(self) -> bool:
        return self.role == MANAGER_ROLE

    def in_scope(self, team: str) -> bool:
        """归属范围判断：同班组，或总部管理（覆盖全部班组）。"""
        return self.team == HQ_TEAM or self.team == team


def parse_operator(
    x_operator_name: str | None = Header(default=None),
    x_operator_role: str | None = Header(default=None),
    x_operator_team: str | None = Header(default=None),
) -> Operator | None:
    """从请求头还原操作人；前端对中文做了 encodeURIComponent，这里统一解码。"""
    if not (x_operator_name and x_operator_role and x_operator_team):
        return None
    name = unquote(x_operator_name)
    role = unquote(x_operator_role)
    team = unquote(x_operator_team)
    for account in ACCOUNTS:
        if account["name"] == name and account["role"] == role and account["team"] == team:
            return Operator(name=name, role=role, team=team)
    return None

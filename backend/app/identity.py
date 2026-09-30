"""登录身份解析：前端通过请求头带上当前值班账号，后端按花名册还原人员、班组与岗位。

花名册是演示用的最小账号体系：岗位角色只能由这里决定，前端不能靠改请求头自行提权。
真实项目里这一层会换成会话/令牌解析，业务代码只依赖 current_operator 依赖注入。
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header

# 演示账号：跨班组（巡检一班/二班）、登记人与管理员两种岗位都覆盖到，方便验证权限边界。


@dataclass(frozen=True)
class Operator:
    """当前登录账号：姓名、归属班组、岗位角色（登记人/管理员）。"""

    name: str
    team: str
    role: str  # 登记人 / 管理员

    @property
    def is_manager(self) -> bool:
        return self.role == "管理员"


def _roster() -> dict[str, Operator]:
    return {
        "王登": Operator(name="王登", team="巡检一班", role="登记人"),
        "赵管": Operator(name="赵管", team="巡检一班", role="管理员"),
        "李巡": Operator(name="李巡", team="巡检二班", role="登记人"),
        "钱管": Operator(name="钱管", team="巡检二班", role="管理员"),
    }


ROSTER = _roster()


async def current_operator(
    x_operator: str | None = Header(default=None, alias="X-Operator"),
) -> Operator | None:
    """按请求头里的姓名从花名册取身份；查不到就视为未登录，写操作会被业务层挡回。"""
    if not x_operator:
        return None
    return ROSTER.get(x_operator.strip())

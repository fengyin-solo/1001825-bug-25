"""缺陷登记业务规则：定级权限、班组归属、状态顺序流转与定级历史都收在这里。

口径要点：
- 只有登记本人或归属班组的管理员能改定级、推动状态，跨班组提交一律挡回；
- 状态只能按 待定级→已定级→处置中→已闭环 顺序推进，不允许跳序；
- 严重等级只能取四个标准档位，列表与安全台账都以这里落库的等级为唯一口径；
- 每次定级/流转都以快照形式追加进 history，绝不覆盖历史。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.identity import Operator
from app.store import store

MODULE = "defect"
REQUIRED_FIELDS = ["缺陷编号", "所在管段", "缺陷类别"]
OPTIONAL_FIELDS = ["缺陷位置", "发现日期"]
STATUS_ORDER = ["待定级", "已定级", "处置中", "已闭环"]
SEVERITY_LEVELS = ["轻微", "一般", "严重", "重大"]
# 这两个档位会计入安全台账异常量
ABNORMAL_LEVELS = {"严重", "重大"}
# 动作 → 唯一允许的（原状态, 目标状态），任何跳序都会被挡
ACTION_FLOW: dict[str, tuple[str, str]] = {
    "确认定级": ("待定级", "已定级"),
    "提交处置": ("已定级", "处置中"),
    "提交闭环": ("处置中", "已闭环"),
}
# 定级类动作：必须带合法的严重等级
GRADE_ACTIONS = {"确认定级", "调整定级"}
# 已进入处置阶段后允许在不改变状态的前提下重新定级
REGRADE_FROM = {"已定级", "处置中"}


class Rejected(Exception):
    """业务挡回：blocked 说明卡在哪一项，message 给页面上可读的提示。"""

    def __init__(self, blocked: str, message: str) -> None:
        super().__init__(message)
        self.blocked = blocked
        self.message = message


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


class DefectService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        level: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("缺陷编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if level:
            rows = [row for row in rows if row.get("严重等级") == level]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def history(self, entry_id: int) -> list[dict[str, Any]] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        return list(entry.get("history") or [])

    def create_entry(
        self, values: dict[str, Any], operator: Operator | None
    ) -> dict[str, Any]:
        """登记缺陷：登记人与归属班组只认登录账号，不接受页面自带的值。"""
        self._assert_signed_in(operator, "登记缺陷")
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            raise Rejected("必填字段", f"缺少必填字段：{'、'.join(missing)}")

        rows = store.rows(MODULE)
        code = str(values["缺陷编号"]).strip()
        if any(str(row.get("缺陷编号") or "") == code for row in rows):
            raise Rejected("缺陷编号", f"缺陷编号 {code} 已存在，不能重复登记")

        entry: dict[str, Any] = {
            "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1,
            "缺陷编号": code,
            "严重等级": "",
            "整改结论": "",
            "status": STATUS_ORDER[0],
            "缺陷状态": STATUS_ORDER[0],
            "pending": True,
            "abnormal": False,
            "登记人员": operator.name,
            "归属班组": operator.team,
            "history": [],
        }
        for field in REQUIRED_FIELDS[1:] + OPTIONAL_FIELDS:
            if str(values.get(field) or "").strip():
                entry[field] = str(values[field]).strip()

        entry["history"].append({
            "action": "登记缺陷", "from": "", "to": STATUS_ORDER[0],
            "严重等级": "", "整改结论": "",
            "操作人": operator.name, "归属班组": operator.team, "时间": _now(),
        })
        rows.append(entry)
        return entry

    def run_action(
        self,
        entry_id: int,
        values: dict[str, Any],
        operator: Operator | None,
    ) -> tuple[dict[str, Any], str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            raise Rejected("缺陷记录", f"缺陷记录 {entry_id} 不存在或已归档")

        action = str(values.get("action") or "").strip()
        if action not in ACTION_FLOW and action != "调整定级":
            raise Rejected("可执行动作", f"动作「{action}」不属于缺陷登记可执行范围")

        # 权限先于业务校验：跨班组、非登记人一律不允许落库
        self._assert_can_modify(entry, operator, action)

        level = str(values.get("严重等级") or "").strip()
        if action in GRADE_ACTIONS:
            if not level:
                raise Rejected("严重等级", f"执行「{action}」前必须先选择严重等级")
            if level not in SEVERITY_LEVELS:
                raise Rejected(
                    "严重等级",
                    f"严重等级「{level}」不合法，只能选：{'、'.join(SEVERITY_LEVELS)}",
                )
        else:
            # 流转动作不携带定级变更时沿用现有等级，防止空值把历史定级抹掉
            level = str(entry.get("严重等级") or "").strip()

        current = str(entry.get("status") or "")
        conclusion = str(entry.get("整改结论") or "")
        if action == "调整定级":
            if current not in REGRADE_FROM:
                raise Rejected(
                    "状态顺序",
                    f"当前状态为「{current}」，只有已定级、处置中的缺陷可以调整定级",
                )
            target = current
        else:
            required_from, target = ACTION_FLOW[action]
            if current != required_from:
                raise Rejected(
                    "状态顺序",
                    f"当前状态为「{current}」，「{action}」只能从「{required_from}」发起，"
                    f"状态必须按 {' → '.join(STATUS_ORDER)} 顺序推进",
                )
            if action == "提交闭环":
                conclusion = str(values.get("整改结论") or "").strip()
                if not conclusion:
                    raise Rejected("整改结论", "提交闭环必须填写整改结论，结论会同步到安全台账首页")

        old_status = current
        entry["严重等级"] = level
        if action == "提交闭环":
            entry["整改结论"] = conclusion
        entry["status"] = target
        entry["缺陷状态"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = level in ABNORMAL_LEVELS

        # 只追加，不覆盖：历史定级/结论随快照永久保留
        entry.setdefault("history", []).append({
            "action": action, "from": old_status, "to": target,
            "严重等级": level, "整改结论": conclusion,
            "操作人": operator.name, "归属班组": operator.team, "时间": _now(),
        })
        return entry, f"缺陷记录已{action}"

    def ledger_summary(self) -> dict[str, Any]:
        """安全台账口径：缺陷列表、概览卡片都从这里取数，保证各处条数一致。"""
        rows = store.rows(MODULE)
        by_status = {status: 0 for status in STATUS_ORDER}
        by_level = {level: 0 for level in SEVERITY_LEVELS}
        closed: list[dict[str, Any]] = []
        for row in rows:
            status = str(row.get("status") or "")
            if status in by_status:
                by_status[status] += 1
            level = str(row.get("严重等级") or "")
            if level in by_level:
                by_level[level] += 1
            if status == "已闭环":
                closed.append({
                    "缺陷编号": row.get("缺陷编号"),
                    "所在管段": row.get("所在管段"),
                    "严重等级": level,
                    "整改结论": str(row.get("整改结论") or ""),
                    "归属班组": row.get("归属班组"),
                    "登记人员": row.get("登记人员"),
                })
        closed.sort(key=lambda item: item["缺陷编号"] or "")
        return {
            "total": len(rows),
            "by_status": by_status,
            "by_level": by_level,
            "abnormal": sum(by_level[level] for level in ABNORMAL_LEVELS),
            "pending_close": by_status["待定级"] + by_status["已定级"] + by_status["处置中"],
            "closed": closed,
        }

    # ---- 权限 -------------------------------------------------------------

    @staticmethod
    def _assert_signed_in(operator: Operator | None, action: str) -> None:
        if operator is None:
            raise Rejected(
                "登录身份",
                f"未识别到登录账号，无法{action}；请先在右上角切换到值班账号",
            )

    @staticmethod
    def _assert_can_modify(entry: dict[str, Any], operator: Operator | None, action: str) -> None:
        DefectService._assert_signed_in(operator, action)
        owner_team = str(entry.get("归属班组") or "")
        if operator.team != owner_team:
            raise Rejected(
                "归属班组",
                f"该缺陷归属「{owner_team}」，当前账号归属「{operator.team}」，"
                f"跨班组记录不允许{action}",
            )
        registrar = str(entry.get("登记人员") or "")
        if not operator.is_manager and operator.name != registrar:
            raise Rejected(
                "登记人员",
                f"该缺陷由「{registrar}」登记，只有登记本人或本班组管理员可以{action}",
            )

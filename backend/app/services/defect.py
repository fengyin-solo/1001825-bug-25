"""缺陷登记业务规则：归属权限、状态流转、定级历史与台账口径都收在这里。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services.identity import Operator
from app.store import store

MODULE = "defect"
REQUIRED_FIELDS = ["缺陷编号", "所在管段", "缺陷类别"]
STATUS_ORDER = ["待定级", "已定级", "处置中", "已闭环"]
SEVERITY_LEVELS = ["轻微", "一般", "较大", "重大"]
# 前进动作：当前状态必须等于源状态才允许走到目标状态，保证状态只能按顺序走
TRANSITIONS = {"确认定级": ("待定级", "已定级"), "开始处置": ("已定级", "处置中"), "提交闭环": ("处置中", "已闭环")}
ACTIONS = [*TRANSITIONS, "改定级", "挂起缺陷"]


def permission_failures(operator: Operator, entry: dict[str, Any]) -> list[str]:
    """逐项检查改动权限，返回未通过的校验说明；空列表表示放行。

    放行规则：登记人本人，或管理岗位且记录落在自己归属班组范围内；
    其余情况（含跨班组的管理岗位）都挡回，并说明卡在哪一项。
    """
    owner = str(entry.get("登记人员") or "").strip()
    team = str(entry.get("所属班组") or "").strip()
    if operator.name == owner:
        return []
    failures = [f"①登记人校验：当前账号「{operator.name}」不是该记录登记人「{owner or '—'}」"]
    if operator.is_manager and operator.in_scope(team):
        return []
    if not operator.is_manager:
        failures.append(f"②岗位校验：当前岗位「{operator.role}」不是管理岗位")
    if not operator.in_scope(team):
        failures.append(f"③归属范围校验：记录归属班组「{team or '—'}」，当前账号归属「{operator.team}」")
    return failures


class DefectService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("缺陷编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def history(self, entry_id: int) -> list[dict[str, Any]]:
        return store.history(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any], operator: Operator) -> tuple[dict[str, Any] | None, list[str]]:
        problems = [f"缺少必填字段：{field}" for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        code = str(values.get("缺陷编号") or "").strip()
        rows = store.rows(MODULE)
        if code and any(str(row.get("缺陷编号")) == code for row in rows):
            problems.append(f"缺陷编号 {code} 已存在，不能重复登记")
        if problems:
            return None, problems
        entry: dict[str, Any] = {
            "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1,
            "缺陷编号": code,
            "所在管段": values.get("所在管段"),
            "缺陷类别": values.get("缺陷类别"),
            "缺陷位置": str(values.get("缺陷位置") or ""),
            "严重等级": "",
            "发现日期": str(values.get("发现日期") or datetime.now().date().isoformat()),
            "登记人员": operator.name,
            "所属班组": operator.team,
            "status": STATUS_ORDER[0],
            "pending": True,
            "abnormal": False,
        }
        entry["缺陷状态"] = entry["status"]
        rows.append(entry)
        self._log(entry, operator, "登记缺陷", before=None, note="新登记，等待定级")
        return entry, []

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any],
        operator: Operator | None,
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"缺陷记录 {entry_id} 不存在或已归档"
        if operator is None:
            return None, "未识别到有效操作账号，请先在页面头部选择当前账号"
        if action not in ACTIONS:
            return None, f"动作「{action}」不属于缺陷登记可执行范围（可执行：{'、'.join(ACTIONS)}）"
        failures = permission_failures(operator, entry)
        if failures:
            return None, f"「{action}」被挡回，卡在以下校验：" + "；".join(failures)

        before = {"严重等级": entry.get("严重等级"), "status": entry.get("status")}

        if action in TRANSITIONS:
            source, _ = TRANSITIONS[action]
            current = str(entry.get("status"))
            if current != source:
                return None, (
                    f"「{action}」被挡回，卡在状态顺序校验：状态只能按 {' → '.join(STATUS_ORDER)} 顺序流转，"
                    f"当前状态「{current}」，该动作要求当前状态为「{source}」"
                )

        if action in ("确认定级", "改定级"):
            level = str(values.get("严重等级") or "").strip()
            if level not in SEVERITY_LEVELS:
                return None, f"「{action}」被挡回，卡在严重等级校验：严重等级必填，且只能是 {'、'.join(SEVERITY_LEVELS)}"
            if action == "改定级" and str(entry.get("status")) not in ("已定级", "处置中"):
                return None, f"「改定级」被挡回，卡在状态校验：只有已定级、处置中的记录允许改定级，当前状态「{entry.get('status')}」"
            entry["严重等级"] = level

        if action == "提交闭环":
            conclusion = str(values.get("整改结论") or "").strip()
            if not conclusion:
                return None, "「提交闭环」被挡回，卡在整改结论校验：整改结论必填，闭环后要落到安全台账"
            entry["整改结论"] = conclusion
            entry["闭环时间"] = datetime.now().date().isoformat()

        if action in TRANSITIONS:
            entry["status"] = TRANSITIONS[action][1]

        if action == "挂起缺陷":
            entry["abnormal"] = True
            reason = str(values.get("挂起原因") or "").strip()
            if reason:
                entry["挂起原因"] = reason

        # 列表字段与系统字段同源同步，保证各入口看到的等级与状态一致
        entry["缺陷状态"] = entry["status"]
        entry["pending"] = entry["status"] != STATUS_ORDER[-1]

        note = ""
        if action == "提交闭环":
            note = str(entry.get("整改结论") or "")
        elif action == "挂起缺陷":
            note = str(values.get("挂起原因") or "").strip() or "挂起，暂不流转"
        self._log(entry, operator, action, before=before, note=note)
        return entry, f"缺陷记录已{action}"

    def ledger(self) -> dict[str, Any]:
        """安全台账：与缺陷列表同一份数据汇总，保证条数对得上。"""
        rows = store.rows(MODULE)
        severity = [
            {"等级": level, "条数": sum(1 for row in rows if (str(row.get("严重等级") or "").strip() or "未定级") == level)}
            for level in ["未定级", *SEVERITY_LEVELS]
        ]
        status = [
            {"状态": item, "条数": sum(1 for row in rows if row.get("status") == item)}
            for item in STATUS_ORDER
        ]
        conclusions = [
            {
                "缺陷编号": row.get("缺陷编号"),
                "严重等级": row.get("严重等级"),
                "整改结论": row.get("整改结论"),
                "闭环时间": row.get("闭环时间"),
                "登记人员": row.get("登记人员"),
                "所属班组": row.get("所属班组"),
            }
            for row in rows
            if row.get("status") == STATUS_ORDER[-1]
        ]
        conclusions.sort(key=lambda item: str(item.get("闭环时间") or ""), reverse=True)
        return {"total": len(rows), "severity": severity, "status": status, "conclusions": conclusions}

    def _log(
        self,
        entry: dict[str, Any],
        operator: Operator,
        action: str,
        *,
        before: dict[str, Any] | None,
        note: str = "",
    ) -> None:
        store.append_history(MODULE, {
            "entry_id": int(entry.get("id", 0)),
            "缺陷编号": entry.get("缺陷编号"),
            "时间": datetime.now().isoformat(timespec="seconds"),
            "操作人": operator.name,
            "岗位": operator.role,
            "班组": operator.team,
            "动作": action,
            "原等级": (before or {}).get("严重等级") or "—",
            "新等级": entry.get("严重等级") or "—",
            "原状态": (before or {}).get("status") or "—",
            "新状态": entry.get("status"),
            "说明": note,
        })

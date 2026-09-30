"""缺陷登记接口：维护缺陷记录，覆盖确认定级、改定级、提交闭环、挂起缺陷等动作。

注意路由顺序：/export、/ledger、/accounts 必须放在 /{entry_id} 之前，
否则 "export" 会被当成 entry_id 解析直接 422。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.defect import DefectService
from app.services.identity import ACCOUNTS, Operator, parse_operator

router = APIRouter(prefix="/api/defect", tags=["缺陷登记"])

service = DefectService()


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按缺陷编号检索"),
    status: str | None = Query(default=None, description="待定级、已定级、处置中、已闭环"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按缺陷编号与状态过滤缺陷登记列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出缺陷登记清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "defect", "total": total, "items": items}


@router.get("/ledger")
def defect_ledger() -> dict[str, Any]:
    """安全台账：严重等级分布、状态分布与整改结论，全部从缺陷登记同一份数据汇总。"""
    return service.ledger()


@router.get("/accounts")
def list_accounts() -> list[dict[str, str]]:
    """在册账号清单：前端切换账号时按这里展示。"""
    return ACCOUNTS


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条缺陷记录明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"缺陷记录 {entry_id} 不存在或已归档")
    return entry


@router.get("/{entry_id}/history")
def entry_history(entry_id: int) -> dict[str, Any]:
    """单条记录的定级与流转历史：改动之后历史保留，换账号进入看到的也是这条链。"""
    if service.get_entry(entry_id) is None:
        raise HTTPException(status_code=404, detail=f"缺陷记录 {entry_id} 不存在或已归档")
    return {"entry_id": entry_id, "items": service.history(entry_id)}


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload, operator: Operator | None = Depends(parse_operator)) -> ActionResult:
    """登记一条缺陷记录：登记人与所属班组取当前账号，缺字段时说明原因而不是静默丢弃。"""
    if operator is None:
        return ActionResult(ok=False, message="未识别到有效操作账号，请先在页面头部选择当前账号")
    entry, problems = service.create_entry(payload.values, operator)
    if problems:
        return ActionResult(ok=False, message=f"登记被挡回：{'；'.join(problems)}")
    return ActionResult(ok=True, message="缺陷记录已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(
    entry_id: int,
    payload: EntryPayload,
    operator: Operator | None = Depends(parse_operator),
) -> ActionResult:
    """对单条缺陷记录执行动作；越权、跳序、缺项都会被挡回并说明卡在哪一项。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action, payload.values, operator)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)

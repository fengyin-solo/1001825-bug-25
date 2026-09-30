"""缺陷登记接口：维护缺陷记录与定级动作，权限、状态顺序与整改结论由业务层统一把关。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.identity import Operator, current_operator
from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.defect import DefectService, Rejected, SEVERITY_LEVELS, STATUS_ORDER

router = APIRouter(prefix="/api/defect", tags=["缺陷登记"])

service = DefectService()

LIST_FIELDS = ["缺陷编号", "所在管段", "缺陷类别", "缺陷位置", "严重等级", "发现日期", "登记人员", "归属班组", "缺陷状态"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按缺陷编号检索"),
    status: str | None = Query(default=None, description="待定级、已定级、处置中、已闭环"),
    level: str | None = Query(default=None, description="轻微、一般、严重、重大"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按缺陷编号、状态与严重等级过滤；所有入口看到的等级都来自同一份记录。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, level=level, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/ledger")
def defect_ledger() -> dict[str, Any]:
    """缺陷安全台账：等级分布、闭环整改结论与概览/列表同源，条数永远对得上。"""
    return {
        "module": "defect",
        "statuses": STATUS_ORDER,
        "levels": SEVERITY_LEVELS,
        **service.ledger_summary(),
    }


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出缺陷登记清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "defect", "total": total, "items": items}


@router.get("/{entry_id}/history")
def get_history(entry_id: int) -> dict[str, Any]:
    """读取一条缺陷的定级/流转历史；历史只追加不改写，换账号登录也能看到。"""
    history = service.history(entry_id)
    if history is None:
        raise HTTPException(status_code=404, detail=f"缺陷记录 {entry_id} 不存在或已归档")
    return {"entry_id": entry_id, "total": len(history), "items": history}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条缺陷记录明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"缺陷记录 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(
    payload: EntryPayload,
    operator: Operator | None = Depends(current_operator),
) -> ActionResult:
    """登记缺陷；登记人与归属班组取登录账号，越权或缺字段会说明卡在哪一项。"""
    try:
        entry = service.create_entry(payload.values, operator)
    except Rejected as rejected:
        return ActionResult(ok=False, message=rejected.message, blocked=rejected.blocked)
    return ActionResult(ok=True, message="缺陷记录已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(
    entry_id: int,
    payload: EntryPayload,
    operator: Operator | None = Depends(current_operator),
) -> ActionResult:
    """执行定级/调整定级/提交处置/提交闭环：跨班组、非登记人、跳序、缺结论都会被挡回。"""
    try:
        entry, message = service.run_action(entry_id, payload.values, operator)
    except Rejected as rejected:
        return ActionResult(ok=False, message=rejected.message, blocked=rejected.blocked)
    return ActionResult(ok=True, message=message, entry=entry)

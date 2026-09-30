"""内存数据仓库：给每个业务模块准备一份可筛选、可流转的示例数据。

真实项目里这里会换成数据库访问层；当前实现只依赖标准库，保证克隆下来就能起。
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.seed import SEED_ROWS


class Store:
    def __init__(self) -> None:
        # 深拷贝：缺陷定级历史是嵌套结构，浅拷贝会让重启后重新播种的多个 Store 视图共享同一份列表
        self._tables: dict[str, list[dict[str, Any]]] = {
            name: deepcopy(rows) for name, rows in SEED_ROWS.items()
        }

    def module_names(self) -> list[str]:
        return sorted(self._tables)

    def rows(self, module: str) -> list[dict[str, Any]]:
        return self._tables.setdefault(module, [])

    def find(self, module: str, entry_id: int) -> dict[str, Any] | None:
        for row in self.rows(module):
            if int(row.get("id", 0)) == entry_id:
                return row
        return None

    def overview(self) -> dict[str, object]:
        modules: list[dict[str, object]] = []
        for name in self.module_names():
            rows = self.rows(name)
            if name == "defect":
                # 异常量与安全台账共用同一口径：严重、重大缺陷计入；不能只看提交时留下的旧标记
                abnormal = sum(1 for row in rows if str(row.get("严重等级") or "") in {"严重", "重大"})
                pending = sum(1 for row in rows if row.get("status") != "已闭环")
            else:
                abnormal = sum(1 for row in rows if row.get("abnormal"))
                pending = sum(1 for row in rows if row.get("pending"))
            modules.append({
                "name": name,
                "created": len(rows),
                "pending": pending,
                "abnormal": abnormal,
            })
        cards = [
            {"label": "业务模块", "value": len(modules)},
            {"label": "今日新增", "value": sum(int(item["created"]) for item in modules)},
            {"label": "待处理", "value": sum(int(item["pending"]) for item in modules)},
            {"label": "异常量", "value": sum(int(item["abnormal"]) for item in modules)},
        ]
        return {"cards": cards, "modules": modules}


store = Store()

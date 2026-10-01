"""内存数据仓库：给每个业务模块准备一份可筛选、可流转的示例数据。

真实项目里这里会换成数据库访问层；当前实现只依赖标准库，保证克隆下来就能起。
"""
from __future__ import annotations

from typing import Any

from app.seed import SEED_ROWS

# 各模块用于标识同一业务对象的编号字段；概览统计按该字段去重，
# 同一编号的重复行只计一次。未登记的模块退化为按行计数。
MODULE_CODE_FIELDS: dict[str, str] = {
    "windfarm": "场站编码",
    "turbine": "机组编号",
    "blade": "叶片编号",
    "gearbox": "齿轮箱编号",
    "generator": "发电机编号",
    "pitch": "系统编号",
    "yaw": "系统编号",
    "metmast": "塔架编号",
    "collector": "线路编号",
    "substation": "站区编号",
    "forecast": "预测单号",
    "vibration": "监测编号",
    "defect": "缺陷编号",
    "maintjob": "任务编号",
    "spare": "领用单号",
    "patrol": "巡视单号",
    "accept": "验收单号",
    "settle": "结算单号",
}


class Store:
    def __init__(self) -> None:
        self._tables: dict[str, list[dict[str, Any]]] = {
            name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()
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

    @staticmethod
    def _count_distinct(rows: list[dict[str, Any]], code_field: str | None, predicate) -> int:
        """按业务编号去重计数；编号字段缺失时退回按行计数，保证口径稳定。"""
        if code_field is None:
            return sum(1 for row in rows if predicate(row))
        codes = {
            str(row.get(code_field) or "").strip()
            for row in rows
            if predicate(row) and str(row.get(code_field) or "").strip()
        }
        return len(codes)

    def module_stats(self, module: str) -> dict[str, int]:
        """单个模块的看板指标：同一业务编号的多行只计一次。"""
        rows = self.rows(module)
        code_field = MODULE_CODE_FIELDS.get(module)
        stats = {
            "created": self._count_distinct(rows, code_field, lambda row: True),
            "pending": self._count_distinct(rows, code_field, lambda row: row.get("pending")),
            "abnormal": self._count_distinct(rows, code_field, lambda row: row.get("abnormal")),
        }
        # 机组页需要按内部状态再分桶；同样按机组编号去重，和列表、概览同口径。
        if module == "turbine":
            stats["running"] = self._count_distinct(
                rows, code_field, lambda row: row.get("status") == "运行中"
            )
            stats["fault"] = self._count_distinct(
                rows, code_field, lambda row: row.get("status") == "故障停机"
            )
            stats["retired"] = self._count_distinct(
                rows, code_field, lambda row: row.get("status") == "已退役"
            )
        return stats

    def overview(self) -> dict[str, object]:
        modules: list[dict[str, object]] = []
        for name in self.module_names():
            stats = self.module_stats(name)
            modules.append({
                "name": name,
                "created": stats["created"],
                "pending": stats["pending"],
                "abnormal": stats["abnormal"],
            })
        cards = [
            {"label": "业务模块", "value": len(modules)},
            {"label": "今日新增", "value": sum(int(item["created"]) for item in modules)},
            {"label": "待处理", "value": sum(int(item["pending"]) for item in modules)},
            {"label": "异常量", "value": sum(int(item["abnormal"]) for item in modules)},
        ]
        return {"cards": cards, "modules": modules}


store = Store()

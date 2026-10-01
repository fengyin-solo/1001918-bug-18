"""内存数据仓库：给每个业务模块准备一份可筛选、可流转的示例数据。

真实项目里这里会换成数据库访问层；当前实现只依赖标准库，保证克隆下来就能起。
"""
from __future__ import annotations

from typing import Any

from app.seed import SEED_ROWS

# 各模块的业务编号字段；汇总待处理/异常/新增时按编号去重，同一编号只算一次。
# 没配到的模块退化为按记录 id 去重，不会漏统计。
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


def _distinct_keys(rows: list[dict[str, Any]], module: str) -> set[Any]:
    """统计口径：同一业务编号（如同一台机组）只算一次。"""
    code_field = MODULE_CODE_FIELDS.get(module)
    keys: set[Any] = set()
    for row in rows:
        if code_field and str(row.get(code_field) or "").strip():
            keys.add(str(row[code_field]).strip())
        else:
            keys.add(row.get("id"))
    return keys


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

    def overview(self) -> dict[str, object]:
        modules: list[dict[str, object]] = []
        for name in self.module_names():
            rows = self.rows(name)
            pending_rows = [row for row in rows if row.get("pending")]
            abnormal_rows = [row for row in rows if row.get("abnormal")]
            modules.append({
                "name": name,
                "created": len(_distinct_keys(rows, name)),
                "pending": len(_distinct_keys(pending_rows, name)),
                "abnormal": len(_distinct_keys(abnormal_rows, name)),
            })
        cards = [
            {"label": "业务模块", "value": len(modules)},
            {"label": "今日新增", "value": sum(int(item["created"]) for item in modules)},
            {"label": "待处理", "value": sum(int(item["pending"]) for item in modules)},
            {"label": "异常量", "value": sum(int(item["abnormal"]) for item in modules)},
        ]
        return {"cards": cards, "modules": modules}


store = Store()

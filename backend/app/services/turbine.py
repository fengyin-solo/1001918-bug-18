"""风电机组业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "turbine"
CODE_FIELD = "机组编号"
STATUS_FIELD = "机组状态"
REQUIRED_FIELDS = ["机组编号", "机组机型", "额定功率"]
# 明细中允许修改的字段；机组编号作为业务主键不在编辑范围内
EDITABLE_FIELDS = ["机组机型", "额定功率", "轮毂高度", "所属场站", "投运日期", "累计发电量"]
STATUS_ORDER = ["待投运", "运行中", "故障停机", "已退役"]
ACTION_RULES = {"投运机组": "运行中", "登记停机": "故障停机", "办理退役": "已退役"}
# 会把机组标记为异常的动作
NEGATIVE_ACTIONS = ["登记停机"]
# 合法的状态流转；已退役是终态，任何动作都不能再改
ALLOWED_TRANSITIONS = {
    "待投运": {"运行中"},
    "运行中": {"故障停机", "已退役"},
    "故障停机": {"运行中", "已退役"},
    "已退役": set(),
}


def _present(entry: dict[str, Any]) -> dict[str, Any]:
    """返回给前端前同步展示字段：列表与明细都取同一份记录、同一套口径。"""
    entry[STATUS_FIELD] = entry.get("status")
    return entry


class TurbineService:
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
            rows = [row for row in rows if keyword in str(row.get(CODE_FIELD, ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        page_rows = [_present(dict(row)) for row in rows[start:start + size]]
        return page_rows, total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        return _present(entry) if entry is not None else None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        code = str(values[CODE_FIELD]).strip()
        rows = store.rows(MODULE)
        if any(str(row.get(CODE_FIELD, "")).strip() == code for row in rows):
            return None, f"机组编号 {code} 已存在，同一台机组只允许登记一次"
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in [CODE_FIELD, *EDITABLE_FIELDS]:
            entry[field] = str(values.get(field) or "").strip() or None
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return _present(entry), ""

    def update_entry(
        self, entry_id: int, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        """在原记录上就地修改；任何字段不合法都不动原内容，返回可读说明。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"风电机组 {entry_id} 不存在或已归档"
        if entry.get("status") == STATUS_ORDER[-1]:
            return None, "机组已退役，台账已冻结，不能再修改机型与轮毂高度"

        incoming = {
            field: str(values.get(field) or "").strip()
            for field in EDITABLE_FIELDS
            if field in values
        }
        missing = [
            field for field in REQUIRED_FIELDS if field in incoming and not incoming[field]
        ]
        if missing:
            return None, f"必填字段不能清空：{'、'.join(missing)}，原内容已保留"

        # 全部校验通过后才落库，保存失败时原记录原样保留
        entry.update(incoming)
        return _present(entry), ""

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"风电机组 {entry_id} 不存在或已归档"
        action = action.strip()
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于风电机组可执行范围"

        current = entry.get("status")
        target = ACTION_RULES[action]
        if current == STATUS_ORDER[-1] and target == STATUS_ORDER[-1]:
            # 退役是终态：重复提交同一次退役不再改写记录，直接幂等返回当前状态
            return _present(entry), "该机组已是退役状态，未重复生成退役记录"
        if target not in ALLOWED_TRANSITIONS.get(current, set()):
            return None, f"机组当前为「{current}」，不能执行「{action}」，原状态已保留"

        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return _present(entry), f"风电机组已{action}"

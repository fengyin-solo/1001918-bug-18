"""风电机组业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.store import store

MODULE = "turbine"
REQUIRED_FIELDS = ["机组编号", "机组机型", "额定功率"]
# 详情里允许修改的台账字段；机组编号是唯一标识，不允许改动。
EDITABLE_FIELDS = ["机组机型", "轮毂高度", "额定功率", "所属场站", "投运日期", "累计发电量"]
STATUS_ORDER = ["待投运", "运行中", "故障停机", "已退役"]
RETIRED_STATUS = STATUS_ORDER[-1]
# 键是动作，值是该动作允许从哪些状态发起；退役是终态，任何动作都不能把它打回运行中。
ACTION_RULES: dict[str, dict[str, Any]] = {
    "投运机组": {"target": "运行中", "from": {"待投运", "故障停机"}, "abnormal": False},
    "登记停机": {"target": "故障停机", "from": {"待投运", "运行中"}, "abnormal": True},
    "办理退役": {"target": RETIRED_STATUS, "from": {"待投运", "运行中", "故障停机"}, "abnormal": False},
}
# 列表与详情展示的状态列，必须和内部 status 始终取同一份值。
DISPLAY_STATUS_FIELD = "机组状态"


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
            rows = [row for row in rows if keyword in str(row.get("机组编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def _find_by_code(self, code: str, *, exclude_id: int | None = None) -> dict[str, Any] | None:
        """按机组编号查重：同一批机组编号只允许存在一条记录。"""
        for row in store.rows(MODULE):
            if exclude_id is not None and int(row.get("id", 0)) == exclude_id:
                continue
            if str(row.get("机组编号", "")).strip() == code:
                return row
        return None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        code = str(values["机组编号"]).strip()
        if self._find_by_code(code) is not None:
            return None, f"机组编号 {code} 已存在，同一台机组不能重复建档"
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["机组编号"] = code
        entry["status"] = STATUS_ORDER[0]
        entry[DISPLAY_STATUS_FIELD] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, ""

    def update_entry(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """修改机型、轮毂高度等台账字段。

        先在副本上完成全部校验与写入，任何一步失败都不会碰到原记录，页面上原内容得以保留。
        """
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"风电机组 {entry_id} 不存在或已归档"
        unknown = [field for field in values if field not in EDITABLE_FIELDS]
        if unknown:
            return None, f"机组机型、轮毂高度之外的字段不支持在此修改：{'、'.join(unknown)}"
        blank = [
            field for field in ("机组机型", "额定功率")
            if field in values and not str(values[field] or "").strip()
        ]
        if blank:
            return None, f"必填字段不能清空：{'、'.join(blank)}"
        updated = deepcopy(entry)
        for field in EDITABLE_FIELDS:
            if field in values:
                updated[field] = values[field]
        # 校验全部通过后才落库：列表与详情看到的始终是同一份完整记录。
        entry.clear()
        entry.update(updated)
        return entry, ""

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str, bool]:
        """执行状态动作，返回 (记录, 说明, 是否真正发生变化)。

        退役是终态且动作幂等：对已退役机组重复提交退役不报错、也不多出任何记录。
        """
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"风电机组 {entry_id} 不存在或已归档", False
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于风电机组可执行范围", False
        rule = ACTION_RULES[action]
        target = rule["target"]
        current = str(entry.get("status") or "")
        if current == RETIRED_STATUS:
            # 终态保护：已退役机组不允许再被投运/停机，重复退役按幂等处理。
            if target == RETIRED_STATUS:
                return entry, "该机组已处于退役状态，无需重复办理", False
            return None, "该机组已办理退役，退役为终态，不能再执行投运或停机", False
        if current not in rule["from"]:
            return None, f"机组当前状态为「{current}」，不允许执行「{action}」", False
        entry["status"] = target
        entry[DISPLAY_STATUS_FIELD] = target
        entry["pending"] = target != RETIRED_STATUS
        entry["abnormal"] = bool(rule["abnormal"])
        return entry, f"风电机组已{action}", True

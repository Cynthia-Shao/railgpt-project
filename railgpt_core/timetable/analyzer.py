from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


def parse_query_intent(query: str) -> dict | None:
    """从问题中提取车次、晚点时间、车站。返回 None 表示未识别到。"""
    train = re.search(r"[GDCKZT]\d+", query.upper())
    delay = re.search(r"(\d+)\s*(?:分钟|min)", query)
    limit = re.search(r"限速\s*(\d+)", query)

    if not train:
        return None

    return {
        "train_id": train.group(),
        "delay_minutes": int(delay.group(1)) if delay else 0,
        "speed_limit": int(limit.group(1)) if limit else 0,
        "raw_query": query,
    }


class TimetableAnalyzer:
    def __init__(self, xlsx_path: str | None = None) -> None:
        if xlsx_path is None:
            xlsx_path = str(Path(__file__).parent.parent.parent.parent / "planned_timetable.xlsx")
        self.xlsx_path = xlsx_path
        self.df: pd.DataFrame | None = None
        self.station_pairs: list[tuple[str, str, str]] = []  # [(name, arr_col, dep_col), ...]
        self.station_names: list[str] = []

        if Path(xlsx_path).exists():
            self._load()

    def _load(self) -> None:
        raw = pd.read_excel(self.xlsx_path, index_col=0)
        self.df = raw.fillna("")

        # 提取车站名和列对应关系
        cols = list(self.df.columns)
        self.station_pairs = []
        for i in range(0, len(cols), 2):
            name = cols[i]
            arr_col = cols[i]
            dep_col = cols[i + 1] if i + 1 < len(cols) else cols[i]
            self.station_pairs.append((name, arr_col, dep_col))
        self.station_names = [s[0] for s in self.station_pairs]

    @property
    def loaded(self) -> bool:
        return self.df is not None and not self.df.empty

    def get_train_schedule(self, train_id: str) -> list[dict] | None:
        if not self.loaded or train_id not in self.df.index:
            return None
        row = self.df.loc[train_id]
        schedule: list[dict] = []
        for name, arr_col, dep_col in self.station_pairs:
            arr = row[arr_col]
            dep = row[dep_col]
            if arr == "":
                continue
            arr = float(arr)
            dep = float(dep) if dep != "" else arr
            schedule.append({
                "station": name,
                "arrival": arr,
                "departure": dep,
                "stops": dep != arr,
            })
        return schedule

    def find_conflicts(
        self,
        train_id: str,
        delay_minutes: int,
        start_station: str | None = None,
    ) -> dict:
        schedule = self.get_train_schedule(train_id)
        if schedule is None:
            return {"error": f"Train {train_id} not found in timetable"}

        # 确定从哪个站开始晚点
        start_idx = 0
        if start_station:
            for i, s in enumerate(schedule):
                if start_station in s["station"]:
                    start_idx = i
                    break

        conflicts: list[dict] = []
        affected_stations: set[str] = set()

        # 对晚点后经过的每个车站，检查冲突
        for i in range(start_idx, len(schedule)):
            stn = schedule[i]
            delayed_arr = stn["arrival"] + delay_minutes
            delayed_dep = stn["departure"] + delay_minutes

            # 遍历所有其他列车
            for other_id in self.df.index:
                if other_id == train_id:
                    continue
                other_sched = self.get_train_schedule(other_id)
                if other_sched is None:
                    continue
                if i >= len(other_sched):
                    continue

                other_stn = other_sched[i]
                # 跳过不经过此站的车
                if other_stn["arrival"] == "" or float(other_stn["arrival"]) == 0:
                    continue

                other_arr = float(other_stn["arrival"])
                other_dep = float(other_stn["departure"])

                # 冲突条件：时间窗口重叠（简化为 5 分钟安全间隔）
                gap = 5
                overlap = not (
                    delayed_dep + gap < other_arr
                    or other_dep + gap < delayed_arr
                )
                if overlap:
                    conflicts.append({
                        "other_train": other_id,
                        "station": stn["station"],
                        "original_overlap": f"{int(stn['arrival'])}-{int(stn['departure'])} vs {int(other_arr)}-{int(other_dep)}",
                        "delayed_overlap": f"{int(delayed_arr)}-{int(delayed_dep)} vs {int(other_arr)}-{int(other_dep)}",
                    })
                    affected_stations.add(stn["station"])
                    break  # 每个其他列车只记录一次

        return {
            "train_id": train_id,
            "delay_minutes": delay_minutes,
            "total_conflicts": len(conflicts),
            "conflicts": conflicts,
            "affected_stations": list(affected_stations),
            "schedule": schedule,
        }

    def format_for_prompt(self, analysis: dict) -> str:
        if "error" in analysis:
            return f"[运行图分析] {analysis['error']}"

        lines = [
            f"[运行图分析]",
            f"车次: {analysis['train_id']}",
            f"晚点: {analysis['delay_minutes']} 分钟",
        ]

        # 时间线
        sched = analysis.get("schedule", [])
        if sched:
            lines.append("途经时刻:")
            for s in sched:
                mark = " (停车)" if s["stops"] else ""
                lines.append(f"  {s['station']}: {int(s['arrival'])}→{int(s['departure'])}{mark}")

        # 冲突
        if analysis["total_conflicts"] == 0:
            lines.append("冲突分析: 该晚点不影响其他列车运行。")
        else:
            lines.append(f"冲突分析: 与 {analysis['total_conflicts']} 趟列车在以下车站可能冲突:")
            for c in analysis["conflicts"]:
                lines.append(f"  {c['station']}: {c['other_train']} ({c['delayed_overlap']})")
            lines.append(f"受影响车站: {', '.join(analysis['affected_stations'])}")

        return "\n".join(lines)

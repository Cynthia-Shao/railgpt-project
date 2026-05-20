from __future__ import annotations

from dataclasses import dataclass, field
import re

import pandas as pd

from railgpt_core.timetable.analyzer import TimetableAnalyzer
from railgpt_core.timetable.evaluator import (
    SchedulePlan,
    evaluate_plans,
    search_delay_parameter,
)


@dataclass(slots=True)
class ScenarioEvent:
    event_type: str
    train_id: str = ""
    station: str = ""
    delay_minutes: int = 0
    speed_limit: int = 0
    start_time: int | None = None
    duration_minutes: int | None = None
    end_time: int | None = None
    range_km: int | None = None
    wind_level: int | None = None
    description: str = ""
    affected_trains: list[str] = field(default_factory=list)
    excluded_trains: list[dict] = field(default_factory=list)


def _extract_minutes(query: str, default: int) -> int:
    if "半小时" in query or "半个小时" in query:
        return 30
    match = re.search(r"(\d+)\s*(?:分钟|分|min)", query, re.IGNORECASE)
    return int(match.group(1)) if match else default


def _extract_duration(query: str) -> int | None:
    if "半小时" in query or "半个小时" in query:
        return 30
    match = re.search(r"(?:持续|预计持续|影响)\D{0,6}(\d+)\s*(?:分钟|分|min)", query, re.IGNORECASE)
    if match:
        return int(match.group(1))
    hour_match = re.search(r"(?:持续|预计持续|影响)\D{0,6}(\d+)\s*(?:小时|h)", query, re.IGNORECASE)
    if hour_match:
        return int(hour_match.group(1)) * 60
    return None


def _extract_speed(query: str, default: int) -> int:
    match = re.search(r"(?:限速|降至|速度)\D{0,8}(\d+)", query)
    return int(match.group(1)) if match else default


def _extract_time(query: str) -> int | None:
    match = re.search(r"([01]?\d|2[0-3])\s*[:：]\s*([0-5]\d)", query)
    if match:
        return int(match.group(1)) * 60 + int(match.group(2))
    return None


def _extract_range_km(query: str) -> int | None:
    match = re.search(r"(\d+)\s*(?:km|公里|千米)", query, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _extract_wind_level(query: str) -> int | None:
    chinese = {
        "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
        "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    }
    match = re.search(r"(\d+|[一二三四五六七八九十])\s*级", query)
    if not match:
        return None
    value = match.group(1)
    return int(value) if value.isdigit() else chinese.get(value)


def _extract_train(query: str) -> str:
    match = re.search(r"[GDCKZT]\d+", query.upper())
    return match.group() if match else ""


def _extract_station(query: str, analyzer: TimetableAnalyzer, fallback_index: int = 1) -> str:
    for station in analyzer.station_names:
        if station and station in query:
            return station
    if analyzer.station_names:
        index = min(max(fallback_index, 0), len(analyzer.station_names) - 1)
        return analyzer.station_names[index]
    return ""


def parse_scenario_event(query: str, analyzer: TimetableAnalyzer) -> ScenarioEvent | None:
    """Turn an operational scene into a structured disturbance for the optimizer."""
    if not analyzer.loaded:
        return None

    train_id = _extract_train(query)
    start_time = _extract_time(query)
    duration = _extract_duration(query)
    end_time = start_time + duration if start_time is not None and duration is not None else None

    if any(word in query for word in ("大风", "强风", "横风", "风速", "台风")):
        wind_level = _extract_wind_level(query)
        speed_limit = _extract_speed(query, default=200 if not wind_level or wind_level < 9 else 160)
        return ScenarioEvent(
            event_type="speed_restriction",
            train_id=train_id,
            station=_extract_station(query, analyzer, fallback_index=2),
            speed_limit=speed_limit,
            start_time=start_time,
            duration_minutes=duration,
            end_time=end_time,
            range_km=_extract_range_km(query),
            wind_level=wind_level,
            description="大风天气触发区间临时限速",
        )

    if any(word in query for word in ("降雨", "暴雨", "大雨", "积水", "雨量")):
        return ScenarioEvent(
            event_type="speed_restriction",
            train_id=train_id,
            station=_extract_station(query, analyzer, fallback_index=2),
            speed_limit=_extract_speed(query, default=160),
            start_time=start_time,
            duration_minutes=duration,
            end_time=end_time,
            range_km=_extract_range_km(query),
            description="降雨天气触发区间临时限速",
        )

    if any(word in query for word in ("晚点",)):
        return ScenarioEvent(
            event_type="station_delay",
            train_id=train_id,
            station=_extract_station(query, analyzer, fallback_index=1),
            delay_minutes=_extract_minutes(query, default=10),
            start_time=start_time,
            duration_minutes=duration,
            end_time=end_time,
            description="列车晚点导致运行图扰动",
        )

    if any(word in query for word in ("堵门", "车门", "乘客", "旅客", "站台滞留")):
        return ScenarioEvent(
            event_type="station_delay",
            train_id=train_id,
            station=_extract_station(query, analyzer, fallback_index=1),
            delay_minutes=_extract_minutes(query, default=8),
            start_time=start_time,
            duration_minutes=duration,
            end_time=end_time,
            description="旅客或车门事件导致站内停站延长",
        )

    if any(word in query for word in ("异物", "侵限", "护网", "落物")):
        return ScenarioEvent(
            event_type="speed_restriction",
            train_id=train_id,
            station=_extract_station(query, analyzer, fallback_index=2),
            speed_limit=_extract_speed(query, default=120),
            start_time=start_time,
            duration_minutes=duration,
            end_time=end_time,
            range_km=_extract_range_km(query),
            description="异物侵限或线路异物触发区间限速",
        )

    return None


def _normalize_station_name(location: str, analyzer: TimetableAnalyzer) -> str:
    text = str(location or "").replace("附近", "").replace("区段", "")
    for station in analyzer.station_names:
        if station and (station in text or text in station):
            return station
    return ""


def apply_strategy_to_event(
    event: ScenarioEvent,
    strategy: dict | None,
    analyzer: TimetableAnalyzer,
) -> ScenarioEvent:
    if not strategy:
        return event

    if strategy.get("event_type") and not event.event_type:
        event.event_type = str(strategy["event_type"])
    if strategy.get("location"):
        normalized_station = _normalize_station_name(str(strategy["location"]), analyzer)
        if normalized_station:
            event.station = normalized_station
    if strategy.get("speed_limit"):
        try:
            event.speed_limit = int(float(strategy["speed_limit"]))
        except (TypeError, ValueError):
            pass
    if strategy.get("range_km"):
        try:
            event.range_km = int(float(strategy["range_km"]))
        except (TypeError, ValueError):
            pass
    if strategy.get("duration_minutes"):
        try:
            event.duration_minutes = int(float(strategy["duration_minutes"]))
        except (TypeError, ValueError):
            pass
    if strategy.get("start_time_minutes") is not None:
        try:
            event.start_time = int(float(strategy["start_time_minutes"]))
        except (TypeError, ValueError):
            pass
    if event.start_time is not None and event.duration_minutes is not None:
        event.end_time = event.start_time + event.duration_minutes
    return event


def _station_index(analyzer: TimetableAnalyzer, station: str) -> int:
    for index, name in enumerate(analyzer.station_names):
        if station and station in name:
            return index
    return min(1, len(analyzer.station_names) - 1)


def _event_station_indices(analyzer: TimetableAnalyzer, event: ScenarioEvent) -> list[int]:
    center = _station_index(analyzer, event.station)
    radius = 1
    if event.range_km and event.range_km >= 80:
        radius = 2
    lo = max(0, center - radius)
    hi = min(len(analyzer.station_names) - 1, center + radius)
    return list(range(lo, hi + 1))


def _train_times_in_indices(
    analyzer: TimetableAnalyzer,
    train_id: str,
    station_indices: list[int],
) -> list[tuple[int, str, float, float]]:
    schedule = analyzer.get_train_schedule(train_id)
    if not schedule:
        return []
    times = []
    for index in station_indices:
        if index >= len(schedule):
            continue
        stop = schedule[index]
        times.append((index, stop["station"], float(stop["arrival"]), float(stop["departure"])))
    return times


def _is_time_affected(times: list[tuple[int, str, float, float]], event: ScenarioEvent) -> bool:
    if event.start_time is None:
        return True

    end_time = event.end_time if event.end_time is not None else event.start_time + 30
    buffer_before = 10
    buffer_after = 10
    window_start = event.start_time - buffer_before
    window_end = end_time + buffer_after

    for _, _, arrival, departure in times:
        if window_start <= arrival <= window_end or window_start <= departure <= window_end:
            return True
    return False


def _find_affected_trains(
    analyzer: TimetableAnalyzer,
    event: ScenarioEvent,
) -> tuple[list[str], list[dict]]:
    if analyzer.df is None:
        return [], []

    station_indices = _event_station_indices(analyzer, event)
    affected: list[str] = []
    excluded: list[dict] = []

    for train_id in analyzer.df.index:
        train = str(train_id)
        times = _train_times_in_indices(analyzer, train, station_indices)
        if not times:
            excluded.append({"train": train, "reason": "不经过影响区段"})
            continue

        if event.train_id and train != event.train_id:
            excluded.append({"train": train, "reason": "非指定扰动车次"})
            continue

        if _is_time_affected(times, event):
            affected.append(train)
        else:
            first_time = min(item[2] for item in times)
            last_time = max(item[3] for item in times)
            excluded.append({
                "train": train,
                "reason": f"通过影响区段时间为{_format_minutes(first_time)}-{_format_minutes(last_time)}，不在事件时间窗内",
            })

    return affected, excluded


def _format_minutes(value: float | int) -> str:
    value = int(round(float(value)))
    return f"{value // 60:02d}:{value % 60:02d}"


def _extra_time_for_speed_limit(speed_limit: int) -> float:
    if speed_limit <= 0:
        return 0
    normal_speed = 350
    slowdown = max(0, normal_speed - speed_limit)
    return round(max(3, slowdown / 50 * 2), 1)


def _generate_timed_speed_plans(
    analyzer: TimetableAnalyzer,
    event: ScenarioEvent,
) -> list[SchedulePlan]:
    if analyzer.df is None:
        return []

    affected, excluded = _find_affected_trains(analyzer, event)
    event.affected_trains = affected
    event.excluded_trains = excluded[:12]
    if not affected:
        return []

    trains = [str(t) for t in analyzer.df.index]
    stations = [s[0] for s in analyzer.station_pairs]
    station_indices = _event_station_indices(analyzer, event)
    first_adjust_idx = min(station_indices)
    extra_time = _extra_time_for_speed_limit(event.speed_limit)

    plan_a = SchedulePlan("A-区段限速延时", trains, stations)
    plan_a.copy_from_original(analyzer)
    for train in affected:
        sched = analyzer.get_train_schedule(train)
        if not sched:
            continue
        for i in range(first_adjust_idx, len(sched)):
            stop = sched[i]
            plan_a.set(train, stop["station"], stop["arrival"] + extra_time, stop["departure"] + extra_time)

    plan_b = SchedulePlan("B-前站扣停分批放行", trains, stations)
    plan_b.copy_from_original(analyzer)
    for rank, train in enumerate(affected):
        sched = analyzer.get_train_schedule(train)
        if not sched:
            continue
        offset = extra_time + rank * 2
        for i in range(first_adjust_idx, len(sched)):
            stop = sched[i]
            plan_b.set(train, stop["station"], stop["arrival"] + offset, stop["departure"] + offset)

    return [plan_a, plan_b]


def search_speed_parameter(
    analyzer: TimetableAnalyzer,
    event: ScenarioEvent,
) -> list[SchedulePlan]:
    """对限速额外时间做网格搜索，返回候选方案列表。"""
    if analyzer.df is None:
        return []

    affected, excluded = _find_affected_trains(analyzer, event)
    event.affected_trains = affected
    event.excluded_trains = excluded[:12]
    if not affected:
        return []

    trains = [str(t) for t in analyzer.df.index]
    stations = [s[0] for s in analyzer.station_pairs]
    station_indices = _event_station_indices(analyzer, event)
    first_adjust_idx = min(station_indices)
    base_extra_time = _extra_time_for_speed_limit(event.speed_limit)

    plans: list[SchedulePlan] = []

    # 额外时间维度搜索
    for et in range(int(base_extra_time), int(base_extra_time) + 7):
        plan = SchedulePlan(f"区段延时-{et}min", trains, stations)
        plan.copy_from_original(analyzer)
        for train in affected:
            sched = analyzer.get_train_schedule(train)
            if not sched:
                continue
            for i in range(first_adjust_idx, len(sched)):
                stop = sched[i]
                plan.set(train, stop["station"],
                         stop["arrival"] + et, stop["departure"] + et)
        plans.append(plan)

    # 基准方案：前站扣停分批放行
    plan_b = SchedulePlan("前站扣停分批放行", trains, stations)
    plan_b.copy_from_original(analyzer)
    for rank, train in enumerate(affected):
        sched = analyzer.get_train_schedule(train)
        if not sched:
            continue
        offset = base_extra_time + rank * 2
        for i in range(first_adjust_idx, len(sched)):
            stop = sched[i]
            plan_b.set(train, stop["station"],
                       stop["arrival"] + offset, stop["departure"] + offset)
    plans.append(plan_b)

    return plans


def generate_plans_for_event(
    analyzer: TimetableAnalyzer,
    event: ScenarioEvent,
    actions: list[str] | None = None,
) -> list[SchedulePlan]:
    if event.event_type == "station_delay" and event.train_id and event.delay_minutes > 0:
        return search_delay_parameter(
            analyzer,
            event.train_id,
            event.delay_minutes,
            start_station=event.station,
            actions=actions,
        )

    if event.event_type == "speed_restriction" and event.speed_limit > 0:
        return search_speed_parameter(analyzer, event)

    return []


def plan_to_dataframe(analyzer: TimetableAnalyzer, plan: SchedulePlan) -> pd.DataFrame:
    """Convert the chosen optimized plan back to the timetable table shape used by UI."""
    if analyzer.df is None:
        return pd.DataFrame()

    adjusted = analyzer.df.copy(deep=True)
    for train_id in plan.train_ids:
        if train_id not in adjusted.index:
            continue
        for station, arr_col, dep_col in analyzer.station_pairs:
            arrival = plan.arrival.get(train_id, {}).get(station)
            departure = plan.departure.get(train_id, {}).get(station)
            if arrival is not None:
                adjusted.loc[train_id, arr_col] = round(float(arrival), 1)
            if departure is not None:
                adjusted.loc[train_id, dep_col] = round(float(departure), 1)
    return adjusted


def optimize_for_scenario(
    analyzer: TimetableAnalyzer,
    query: str,
    strategy: dict | None = None,
    actions: list[str] | None = None,
) -> tuple[ScenarioEvent, list[dict], SchedulePlan, pd.DataFrame] | None:
    event = parse_scenario_event(query, analyzer)
    if event is None:
        return None
    event = apply_strategy_to_event(event, strategy, analyzer)

    plans = generate_plans_for_event(analyzer, event, actions=actions)
    if not plans:
        return None

    results = evaluate_plans(analyzer, plans)
    if not results:
        return None

    best_name = results[0].get("name")
    best_plan = next((plan for plan in plans if plan.name == best_name), plans[0])
    adjusted = plan_to_dataframe(analyzer, best_plan)
    return event, results, best_plan, adjusted


def format_optimizer_context(event: ScenarioEvent, results: list[dict]) -> str:
    lines = [
        "[算法优化结果]",
        f"事件类型: {event.description or event.event_type}",
        f"影响位置: {event.station or '未指定'}",
    ]
    if event.start_time is not None:
        end_time = event.end_time if event.end_time is not None else event.start_time + 30
        lines.append(f"事件时间窗: {_format_minutes(event.start_time)}-{_format_minutes(end_time)}")
    if event.range_km:
        lines.append(f"影响范围: 附近约 {event.range_km} km")
    if event.wind_level:
        lines.append(f"风力等级: {event.wind_level} 级")
    if event.delay_minutes:
        lines.append(f"扰动时长: {event.delay_minutes} 分钟")
    if event.speed_limit:
        lines.append(f"限速值: {event.speed_limit} km/h")
    if event.affected_trains:
        lines.append(f"算法判定受影响列车: {', '.join(event.affected_trains)}")
    if event.excluded_trains:
        sample = "; ".join(f"{item['train']}({item['reason']})" for item in event.excluded_trains[:5])
        lines.append(f"排除示例: {sample}")

    lines.append("候选方案评分:")
    for item in results:
        lines.append(
            f"- {item.get('name', '?')}: score={item.get('score', 0)}, "
            f"TDT={item.get('TDT', '-')}, affected={item.get('affected_trains', '-')}, "
            f"TPMD={item.get('TPMD', '-')}"
        )
    if results:
        lines.append(f"算法推荐: {results[0].get('name', '?')}")
    return "\n".join(lines)

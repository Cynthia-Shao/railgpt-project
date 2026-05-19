"""
RailDPT 应急调度方案量化评估模型
参考：理论建模.docx 第二章
四层架构：约束校验 → 指标计算 → 归一化 → 综合打分
"""

from __future__ import annotations

import math

from railgpt_core.timetable.analyzer import TimetableAnalyzer


class SchedulePlan:
    """一个调度调整方案。存储所有列车在所有站的到达/出发时刻。"""
    def __init__(self, name: str, train_ids: list[str], station_names: list[str]):
        self.name = name
        self.train_ids = train_ids
        self.station_names = station_names
        # arr[train_id][station_name] = arrival_time (float)
        self.arrival: dict[str, dict[str, float]] = {t: {} for t in train_ids}
        # dep[train_id][station_name] = departure_time (float)
        self.departure: dict[str, dict[str, float]] = {t: {} for t in train_ids}

    def set(self, train_id: str, station: str, arrival: float, departure: float):
        self.arrival[train_id][station] = arrival
        self.departure[train_id][station] = departure

    def copy_from_original(self, analyzer: TimetableAnalyzer):
        """从运行图分析器复制原始时刻表。"""
        for t in self.train_ids:
            sched = analyzer.get_train_schedule(t)
            if sched is None:
                continue
            for s in sched:
                self.set(t, s["station"], s["arrival"], s["departure"])


# ========== 第1层：约束校验 ==========

HEADWAY_DEP = 3       # 最小出发间隔 (min)
HEADWAY_ARR = 3       # 最小到达间隔 (min)
HEADWAY_SEC = 3       # 最小区间追踪间隔 (min)
MIN_DWELL = 2         # 最小停站时间 (min)
MIN_RUN_TIME = 5      # 最小区间纯运行时间 (min)，简化默认值


def check_constraints(plan: SchedulePlan) -> dict:
    """
    返回: { "passed": bool, "violations": [{type, train, station, detail}, ...] }
    """
    violations: list[dict] = []
    trains = plan.train_ids
    stations = plan.station_names

    for j, stn in enumerate(stations):
        # 收集该站所有车的时刻
        at_station = []
        for t in trains:
            arr = plan.arrival[t].get(stn)
            dep = plan.departure[t].get(stn)
            if arr is not None and dep is not None:
                at_station.append((t, arr, dep))

        at_station.sort(key=lambda x: x[1])  # 按到达时刻排序

        for i in range(len(at_station)):
            t_i, a_i, d_i = at_station[i]

            # 最小停站时间
            dwell = d_i - a_i
            if dwell < MIN_DWELL:
                violations.append({
                    "type": "dwell", "train": t_i, "station": stn,
                    "detail": f"Dwell {dwell:.0f}min < {MIN_DWELL}min",
                })

            if i + 1 < len(at_station):
                t_next, a_next, d_next = at_station[i + 1]
                # 到达间隔
                if a_next - a_i < HEADWAY_ARR:
                    violations.append({
                        "type": "arrival_headway", "train": f"{t_next}/{t_i}",
                        "station": stn,
                        "detail": f"Arr gap {a_next-a_i:.0f}min < {HEADWAY_ARR}min",
                    })
                # 出发间隔
                if d_next - d_i < HEADWAY_DEP:
                    violations.append({
                        "type": "departure_headway", "train": f"{t_next}/{t_i}",
                        "station": stn,
                        "detail": f"Dep gap {d_next-d_i:.0f}min < {HEADWAY_DEP}min",
                    })

    return {
        "passed": len(violations) == 0,
        "violations": violations,
    }


# ========== 第2层：指标计算 ==========

# 默认载客量（人/列），复兴号CR400约576人
DEFAULT_CAPACITY = 576


def compute_metrics(
    plan: SchedulePlan,
    original: SchedulePlan | None = None,
    capacities: dict[str, float] | None = None,
) -> dict:
    """
    返回 7 个指标：TDT, ADT, TPMD, TAP, VFD, SD, SRT。
    其中 SRT 需要 event_start_time 参数，这里用所有晚点列车的最早晚点作为近似。
    """
    if capacities is None:
        capacities = {t: DEFAULT_CAPACITY for t in plan.train_ids}

    trains = plan.train_ids
    n_stations = len(plan.station_names)
    last_station = plan.station_names[-1]

    # 收集终到晚点
    delays: dict[str, float] = {}
    all_deviations: list[float] = []

    for t in trains:
        orig_arr = original.arrival[t].get(last_station) if original else None
        adj_arr = plan.arrival[t].get(last_station)
        if orig_arr is not None and adj_arr is not None:
            d = max(0, adj_arr - orig_arr)
            delays[t] = d
        else:
            delays[t] = 0.0

        # 计划调整幅度：每个站的出发偏离
        if original:
            for stn in plan.station_names:
                o_dep = original.departure[t].get(stn)
                a_dep = plan.departure[t].get(stn)
                if o_dep is not None and a_dep is not None:
                    all_deviations.append(abs(a_dep - o_dep))

    delayed_trains = {t: d for t, d in delays.items() if d > 0}
    N_delayed = len(delayed_trains)

    # TDT: 总晚点时间
    TDT = sum(delayed_trains.values())

    # ADT: 平均晚点时间
    ADT = TDT / N_delayed if N_delayed > 0 else 0.0

    # TPMD: 旅客总延误时间
    TPMD = sum(capacities.get(t, DEFAULT_CAPACITY) * d for t, d in delayed_trains.items())

    # TAP: 受影响旅客总数
    TAP = sum(capacities.get(t, DEFAULT_CAPACITY) for t in delayed_trains)

    # VFD: 终到晚点时间方差
    if N_delayed > 1:
        mean_d = ADT
        VFD = sum((d - mean_d) ** 2 for d in delayed_trains.values()) / N_delayed
    else:
        VFD = 0.0

    # SD: 计划调整幅度
    SD = sum(all_deviations)

    # SRT: 系统恢复时间（近似：最晚终到-最早晚点）
    event_start = min(delayed_trains.values()) if delayed_trains else 0
    last_finish = max(delays.values()) if delays else 0
    SRT = max(0, last_finish - event_start)

    return {
        "TDT": round(TDT, 1),
        "ADT": round(ADT, 1),
        "TPMD": round(TPMD, 1),
        "TAP": round(TAP, 1),
        "VFD": round(VFD, 1),
        "SD": round(SD, 1),
        "SRT": round(SRT, 1),
        "affected_trains": N_delayed,
    }


# ========== 第3层：归一化 ==========

def normalize_metrics(metrics_list: list[dict]) -> list[dict]:
    """Min-Max 归一化，将多个方案的指标映射到 [0, 1]。"""
    keys = ["TDT", "ADT", "TPMD", "TAP", "VFD", "SD", "SRT"]
    result = []
    for m in metrics_list:
        result.append({k: m[k] for k in keys})

    for k in keys:
        vals = [m[k] for m in metrics_list]
        v_min = min(vals)
        v_max = max(vals)
        if v_max == v_min:
            for r in result:
                r[k + "_norm"] = 1.0
        else:
            for i, m in enumerate(result):
                m[k + "_norm"] = round((v_max - metrics_list[i][k]) / (v_max - v_min), 4)

    for i, r in enumerate(result):
        result[i]["affected_trains"] = metrics_list[i]["affected_trains"]
    return result


# ========== 第4层：综合打分 ==========

DEFAULT_WEIGHTS = {
    "TDT_norm": 0.20,
    "ADT_norm": 0.10,
    "TPMD_norm": 0.20,
    "TAP_norm": 0.15,
    "VFD_norm": 0.10,
    "SD_norm": 0.10,
    "SRT_norm": 0.15,
}


def compute_scores(normalized: list[dict], weights: dict | None = None) -> list[dict]:
    """计算每个方案的综合得分。"""
    if weights is None:
        weights = DEFAULT_WEIGHTS
    scores = []
    for m in normalized:
        score = sum(weights[k] * m.get(k, 0) for k in weights)
        scores.append({
            "TDT": m["TDT"],
            "ADT": m["ADT"],
            "TPMD": m["TPMD"],
            "TAP": m["TAP"],
            "VFD": m["VFD"],
            "SD": m["SD"],
            "SRT": m["SRT"],
            "affected_trains": m["affected_trains"],
            "score": round(score, 4),
            "TDT_norm": m.get("TDT_norm", 0),
            "TPMD_norm": m.get("TPMD_norm", 0),
        })
    return scores


# ========== 场景1：单列车晚点方案生成 ==========

def generate_delay_plans(
    analyzer: TimetableAnalyzer,
    train_id: str,
    delay_minutes: float,
    start_station: str = "",
) -> list[SchedulePlan]:
    """为单列车晚点场景生成3个候选调整方案。"""
    sched = analyzer.get_train_schedule(train_id)
    if sched is None:
        return []

    # 找起始站索引
    start_idx = 0
    for i, s in enumerate(sched):
        if start_station and start_station in s["station"]:
            start_idx = i
            break

    plans = []
    trains = [t for t in analyzer.df.index]
    stations = [s[0] for s in analyzer.station_pairs]

    # 方案A：所有后续车站直接延迟（无其他调整）
    plan_a = SchedulePlan("A-延迟传播", trains, stations)
    plan_a.copy_from_original(analyzer)
    for i in range(start_idx, len(sched)):
        stn = sched[i]
        plan_a.set(train_id, stn["station"],
                   stn["arrival"] + delay_minutes,
                   stn["departure"] + delay_minutes)
    plans.append(plan_a)

    # 方案B：延迟 + 压缩停站时间（每个停站压缩到2min最小）
    plan_b = SchedulePlan("B-压缩停站", trains, stations)
    plan_b.copy_from_original(analyzer)
    accumulated = delay_minutes
    for i in range(start_idx, len(sched)):
        stn = sched[i]
        new_arr = stn["arrival"] + accumulated
        if stn["stops"] and (stn["departure"] - stn["arrival"]) > 2:
            new_dep = new_arr + 2  # 压缩到2分钟
            saved = (stn["departure"] - stn["arrival"]) - 2
        else:
            new_dep = new_arr + max(0, stn["departure"] - stn["arrival"])
            saved = 0
        plan_b.set(train_id, stn["station"], new_arr, new_dep)
        accumulated = max(0, accumulated - saved)
    plans.append(plan_b)

    # 方案C：扣停冲突列车（每个冲突车站让冲突车等3分钟）
    plan_c = SchedulePlan("C-扣停冲突", trains, stations)
    plan_c.copy_from_original(analyzer)
    conflicts = analyzer.find_conflicts(train_id, int(delay_minutes))
    held_trains = set()
    for c in conflicts.get("conflicts", []):
        ot = c["other_train"]
        if ot not in held_trains:
            held_trains.add(ot)
            other_sched = analyzer.get_train_schedule(ot)
            if other_sched:
                for os in other_sched:
                    plan_c.set(ot, os["station"],
                               os["arrival"] + 3,
                               os["departure"] + 3)
    # 延迟车照常延迟
    for i in range(start_idx, len(sched)):
        stn = sched[i]
        plan_c.set(train_id, stn["station"],
                   stn["arrival"] + delay_minutes,
                   stn["departure"] + delay_minutes)
    plans.append(plan_c)

    return plans


# ========== 场景2：区间限速方案生成 ==========

def generate_speed_restriction_plans(
    analyzer: TimetableAnalyzer,
    section_station: str,   # 限速区间起始站
    limit_speed: float,      # 限速值 (km/h)
    normal_speed: float = 350,  # 正常速度 (km/h)
    deceleration: float = 3000,  # 减速度 (km/h²)
    acceleration: float = 2000,  # 加速度 (km/h²)
) -> list[SchedulePlan]:
    """为区间临时限速场景生成候选调整方案。"""
    # 找到限速区间
    stations = [s[0] for s in analyzer.station_pairs]
    idx = next((i for i, s in enumerate(stations) if section_station in s), -1)
    if idx < 0 or idx + 1 >= len(stations):
        return []

    s_from = stations[idx]
    s_to = stations[idx + 1]

    # 计算限速后的最小运行时间（减速+匀速+加速三阶段）
    d_dec = (normal_speed ** 2 - limit_speed ** 2) / (2 * deceleration)  # 减速距离
    t_dec = (normal_speed - limit_speed) / deceleration * 60  # 减速时间 (min)
    d_acc = (normal_speed ** 2 - limit_speed ** 2) / (2 * acceleration)  # 加速距离
    t_acc = (normal_speed - limit_speed) / acceleration * 60  # 加速时间 (min)
    t_cruise = 2  # 假设匀速段 2 分钟（简化）
    extra_time = round(t_dec + t_cruise + t_acc, 1)

    # 找出经过该区间的所有列车
    affected = []
    for t in analyzer.df.index:
        sched = analyzer.get_train_schedule(t)
        if sched is None or len(sched) <= idx + 1:
            continue
        arr_from = sched[idx]["arrival"]
        arr_to = sched[idx + 1]["arrival"]
        if arr_from and arr_to:
            affected.append(t)

    trains = [t for t in analyzer.df.index]
    plans = []

    # 方案A：所有受影响列车增加限速延时（保持原顺序）
    plan_a = SchedulePlan("A-限速延时", trains, stations)
    plan_a.copy_from_original(analyzer)
    for t in affected:
        sched = analyzer.get_train_schedule(t)
        accumulated = extra_time
        for i in range(idx + 1, len(sched)):
            stn = sched[i]
            plan_a.set(t, stn["station"],
                       stn["arrival"] + accumulated,
                       stn["departure"] + accumulated)
    plans.append(plan_a)

    # 方案B：增加区间前扣停间隔（每天加额外间隔防止追尾）
    plan_b = SchedulePlan("B-增加间隔", trains, stations)
    plan_b.copy_from_original(analyzer)
    stagger = extra_time / max(1, len(affected) - 1)
    for rank, t in enumerate(affected):
        sched = analyzer.get_train_schedule(t)
        offset = extra_time + rank * stagger
        for i in range(idx + 1, len(sched)):
            stn = sched[i]
            plan_b.set(t, stn["station"],
                       sched[i]["arrival"] + offset,
                       sched[i]["departure"] + offset)
    plans.append(plan_b)

    return plans


# ========== 冲突自动消解 ==========

def auto_resolve_conflicts(
    plan: SchedulePlan,
    analyzer: TimetableAnalyzer,
    max_iter: int = 50,
) -> SchedulePlan:
    """迭代消解 headway 冲突，每次推后冲突列车 3 分钟。"""
    for _ in range(max_iter):
        c = check_constraints(plan)
        if c["passed"]:
            break
        fixed = False
        for v in c["violations"]:
            if v["type"] in ("arrival_headway", "departure_headway"):
                # 推后冲突的后车
                t_key = v["train"].split("/")[0]  # "G300/G103" → "G300"
                if t_key in plan.departure:
                    stn = v["station"]
                    if stn in plan.arrival[t_key] and stn in plan.departure[t_key]:
                        plan.arrival[t_key][stn] += 3
                        plan.departure[t_key][stn] += 3
                        fixed = True
                        break
        if not fixed:
            break
    return plan


# ========== 综合评估入口 ==========

def evaluate_plans(
    analyzer: TimetableAnalyzer,
    plans: list[SchedulePlan],
    capacities: dict[str, float] | None = None,
) -> list[dict]:
    """对一个方案列表进行完整四层评估，返回排序后的结果。"""
    results = []
    original = SchedulePlan("original", plans[0].train_ids, plans[0].station_names)
    original.copy_from_original(analyzer)

    for plan in plans:
        metrics = compute_metrics(plan, original, capacities)
        metrics["name"] = plan.name
        metrics["feasible"] = True
        results.append(metrics)

    feasible = [r for r in results if r.get("feasible")]
    if len(feasible) >= 2:
        normalized = normalize_metrics(feasible)
        scored = compute_scores(normalized)
        for r, s in zip(feasible, scored):
            r.update({k: s[k] for k in ["TDT_norm", "TPMD_norm", "score"]})
    elif len(feasible) == 1:
        feasible[0]["score"] = 1.0

    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results


def format_evaluation_table(results: list[dict]) -> str:
    """将评估结果格式化为可读表格。"""
    lines = ["\n[方案评估对比]"]
    header = f"{'方案':<20} {'总分':>6} {'总晚点(min)':>12} {'影响列车':>8} {'旅客延误':>10}"
    lines.append(header)
    lines.append("-" * 62)
    for r in results:
        name = r.get("name", "?")[:18]
        score = r.get("score", 0)
        tdt = r.get("TDT", "-")
        aff = r.get("affected_trains", "-")
        tpmd = r.get("TPMD", "-")
        lines.append(f"{name:<20} {score:>6.3f} {str(tdt):>12} {str(aff):>8} {str(tpmd):>10}")
    lines.append("")
    if results and results[0].get("score", 0) > 0:
        lines.append(f"推荐方案: {results[0].get('name', '?')}")
    return "\n".join(lines)

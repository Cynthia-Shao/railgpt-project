import os
import re
import json
from pathlib import Path
from types import SimpleNamespace

from flask import Flask, request, jsonify
from flask_cors import CORS

# 加载 .env 文件到环境变量
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _key, _, _value = _line.partition("=")
            os.environ[_key.strip()] = _value.strip()

from railgpt_core.llm.rag_service import RAGDispatchService  # noqa: E402
from railgpt_core.llm.router import route_query  # noqa: E402
from railgpt_core.timetable.analyzer import TimetableAnalyzer  # noqa: E402
from railgpt_core.timetable.evaluator import (  # noqa: E402
    SchedulePlan, search_delay_parameter, evaluate_plans, format_evaluation_table,
    generate_speed_restriction_plans, explain_best_plan,
)
from railgpt_core.timetable.analyzer import parse_query_intent as timetable_intent  # noqa: E402
from railgpt_core.timetable.scenario import (  # noqa: E402
    format_optimizer_context,
    optimize_for_scenario,
)

app = Flask(__name__)
CORS(app)

rag_service = RAGDispatchService()
rag_service.timetable = TimetableAnalyzer(str(Path(__file__).parent / "planned_timetable.xlsx"))
_knowledge_loaded = False
_latest_adjusted_timetable = None
_latest_adjustment_meta: dict = {}
_latest_diff_rows: list[dict] = []


def _extract_json_object(text: str) -> dict:
    text = _strip_thinking(text or "")
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _build_strategy_prompt(user_query: str, chunks) -> str:
    context_lines = []
    for index, chunk in enumerate(chunks, start=1):
        priority = "强规则" if chunk.must_follow else "场景/普通规则"
        content = chunk.content[:900]
        context_lines.append(f"[{index}] {priority} | {chunk.title}\n{content}")

    context = "\n\n".join(context_lines) if context_lines else "未检索到规则。"
    return f"""你是高速铁路调度策略分析师。根据用户场景和规则上下文，输出调度策略选项。

要求：
1. 给出2~3个策略选项，每个选项说明思路和预计效果
2. 每个策略标注对应的算法动作标签（用于算法精确计算）
3. 推荐其中一个策略并说明理由
4. 算法动作标签只能是：compress_dwell / delay_propagation / hold_conflicts / speed_restriction
5. 不要输出多余文字，严格按照下方格式输出

输出格式：
【策略选项】
【方案A】方案名称
思路：用一两句话说明这个策略怎么做
预计效果：预估对列车运行的影响
算法动作：compress_dwell

【方案B】方案名称
思路：...
预计效果：...
算法动作：delay_propagation

【推荐】方案X
理由：不超过50字

用户场景：
{user_query}

规则上下文：
{context}
"""


def _parse_strategy_options(llm_text: str) -> dict:
    """从LLM输出中解析策略选项和推荐。"""
    import re

    result: dict = {
        "options": [],
        "recommended": "",
        "recommended_action": "",
        "recommended_reason": "",
        "options_text": llm_text.strip(),
        "_parse_error": False,
    }

    if not llm_text or not llm_text.strip():
        result["_parse_error"] = True
        return result

    text = _strip_thinking(llm_text)

    # 提取所有方案块
    option_pattern = re.findall(
        r"【方案([一二三四五六七八九十A-Za-z]+)】\s*(.*?)\n"
        r"思路[:：]\s*(.*?)\n"
        r"预计效果[:：]\s*(.*?)\n"
        r"算法动作[:：]\s*(\w+)",
        text, re.DOTALL,
    )

    for match in option_pattern:
        label, name, idea, effect, action = match
        result["options"].append({
            "label": f"方案{label}",
            "name": name.strip(),
            "idea": idea.strip(),
            "effect": effect.strip(),
            "action": action.strip(),
        })

    # 提取推荐
    rec_match = re.search(r"【推荐】\s*(方案[一二三四五六七八九十A-Za-z]+)", text)
    if rec_match:
        result["recommended"] = rec_match.group(1).strip()

    reason_match = re.search(r"理由[:：]\s*(.*?)(?:\n|$)", text)
    if reason_match:
        result["recommended_reason"] = reason_match.group(1).strip()

    # 找到推荐方案对应的算法动作
    for opt in result["options"]:
        if opt["label"] == result["recommended"]:
            result["recommended_action"] = opt["action"]
            result["recommended_name"] = opt["name"]
            break

    if not result["options"]:
        result["_parse_error"] = True

    return result


def _strategy_from_rules(user_query: str, chunks) -> dict:
    """调用LLM生成策略选项，返回结构化结果。"""
    prompt = _build_strategy_prompt(user_query, chunks)
    try:
        answer = rag_service.llm_client.chat(
            system_prompt="你是高速铁路调度策略分析师，只按格式输出，不输出多余内容。",
            user_prompt=prompt,
            temperature=0.3,
            max_tokens=600,
        )
    except Exception as exc:
        return {
            "strategy_summary": "大模型策略生成失败，采用算法自动搜索。",
            "rule_basis": f"LLM不可用：{exc}",
            "allowed_actions": ["compress_dwell", "delay_propagation", "hold_conflicts"],
            "forbidden_actions": [],
            "hard_constraints": ["已通过影响区段的列车不可调整", "必须满足安全间隔"],
            "_llm_failed": True,
            "_parsed": None,
        }

    parsed = _parse_strategy_options(answer)
    if parsed["_parse_error"] or not parsed.get("recommended_action"):
        return {
            "strategy_summary": "大模型策略解析失败，采用算法自动搜索。",
            "rule_basis": "策略格式解析失败",
            "allowed_actions": ["compress_dwell", "delay_propagation", "hold_conflicts"],
            "forbidden_actions": [],
            "hard_constraints": ["已通过影响区段的列车不可调整", "必须满足安全间隔"],
            "_parse_error": True,
            "_parsed": parsed,
        }

    return {
        "strategy_summary": f"推荐{parsed['recommended']}：{parsed.get('recommended_name', '')}",
        "rule_basis": parsed.get("recommended_reason", ""),
        "allowed_actions": [parsed["recommended_action"]],
        "forbidden_actions": [],
        "hard_constraints": ["已通过影响区段的列车不可调整", "必须满足安全间隔"],
        "_parsed": parsed,
        "_llm_success": True,
    }


def _ensure_knowledge():
    global _knowledge_loaded
    if not _knowledge_loaded:
        rag_service.load_knowledge()
        _knowledge_loaded = True


def _strip_thinking(text: str) -> str:
    """去除 DeepSeek-R1 等推理模型的 思考 块。"""
    text = re.sub(r"", "", text, flags=re.DOTALL)
    text = re.sub(r"", "", text, flags=re.DOTALL)
    return text.strip()


def _parse_answer(text: str) -> dict:
    """从大模型回复中提取【标记】格式的调度方案。"""
    text = _strip_thinking(text)

    # 提取所有【步骤N】标签
    steps = re.findall(r"【步骤\d+】(.*?)(?=(?:【步骤\d+】|【[^步]|$))", text, re.DOTALL)
    steps = [s.strip() for s in steps if s.strip()]

    # 提取方案标题
    title_match = re.search(r"【方案[一二三]】(.*?)(?=(?:【步骤|【方案|【建议|【注意|$))", text, re.DOTALL)
    plan_title = title_match.group(1).strip() if title_match else ""

    # 提取注意事项
    note_match = re.search(r"【注意事项】(.*?)(?=$)", text, re.DOTALL)
    note = note_match.group(1).strip() if note_match else ""

    # 清理展示文本：去掉步骤标签
    clean = re.sub(r"【步骤\d+】", "", text)

    return {
        "answer": clean.strip(),
        "plan_title": plan_title,
        "steps": steps,
        "note": note,
    }


def _general_reply(user_query: str) -> dict:
    text = user_query.strip()
    if any(word in text for word in ("不对", "错了", "这不对")):
        answer = (
            "你说得对，我刚才的判断需要重新校验。"
            "如果涉及运行图调整，我会优先按地点、时间窗和列车实际通过时刻筛选受影响列车，"
            "不会再默认选第一趟车。"
        )
    elif any(word.lower() in text.lower() for word in ("你好", "您好", "hello", "hi")):
        answer = "你好，我是 RailGPT，可以帮你做铁路调度场景分析、规章检索和运行图调整。"
    else:
        answer = "我在。你可以直接描述调度场景，或者问我铁路调度规则、运行图调整方案。"

    return {
        "answer": answer,
        "plan": {"title": "", "steps": [], "note": ""},
        "references": [],
        "optimizer": {"has_adjusted_timetable": False, "best_plan": "", "metrics": [], "meta": {}},
        "diff": [],
        "route": "general_chat",
    }


def _fmt_minutes(value) -> str:
    try:
        minute = int(round(float(value)))
    except (TypeError, ValueError):
        return ""
    return f"{minute // 60:02d}:{minute % 60:02d}"


def _compute_timetable_diff(original_df, adjusted_df) -> list[dict]:
    if original_df is None or adjusted_df is None or original_df.empty or adjusted_df.empty:
        return []

    rows: list[dict] = []
    common_trains = [train for train in adjusted_df.index if train in original_df.index]
    columns = list(adjusted_df.columns)
    for train_id in common_trains:
        changed_stations: list[str] = []
        max_shift = 0.0
        final_shift = 0.0
        first_old = ""
        first_new = ""

        for col in columns:
            old = original_df.loc[train_id, col] if col in original_df.columns else ""
            new = adjusted_df.loc[train_id, col]
            if old == "" or new == "":
                continue
            try:
                old_num = float(old)
                new_num = float(new)
            except (TypeError, ValueError):
                continue
            if old_num != old_num or new_num != new_num:
                continue

            shift = round(new_num - old_num, 1)
            if abs(shift) < 0.01:
                continue

            station = str(col) if not str(col).startswith("Unnamed") else ""
            if station and station not in changed_stations:
                changed_stations.append(station)
            if not first_old:
                first_old = _fmt_minutes(old_num)
                first_new = _fmt_minutes(new_num)
            max_shift = max(max_shift, abs(shift))
            final_shift = shift

        if changed_stations or abs(max_shift) >= 0.01:
            rows.append({
                "train": str(train_id),
                "changed_stations": "、".join(changed_stations[:4]) or "后续区段",
                "station_count": len(changed_stations),
                "max_shift": round(max_shift, 1),
                "final_shift": round(final_shift, 1),
                "first_old": first_old,
                "first_new": first_new,
            })

    rows.sort(key=lambda item: item["max_shift"], reverse=True)
    return rows


def _build_concise_dispatch_answer(
    event,
    optimizer_results: list[dict],
    optimized_plan_name: str,
    diff_rows: list[dict],
    strategy: dict | None = None,
    detail: str = "",
) -> str:
    """生成简洁的调度方案输出，包含百分制评分和可解释性说明。"""
    if not event or not optimizer_results:
        return "未识别到可生成新运行图的扰动事件，请补充地点、时间或影响范围。"

    best = optimizer_results[0]
    score_pct = round(best.get("score", 0) * 100, 1)
    tdt = best.get("TDT", "-")
    affected = best.get("affected_trains", "-")
    tpmd = best.get("TPMD", "-")

    plan_name = best.get("name", optimized_plan_name)

    strategy_summary = ""
    if strategy:
        parsed = strategy.get("_parsed")
        if parsed and parsed.get("recommended_name"):
            strategy_summary = f"{parsed['recommended']}（{parsed['recommended_name']}）"
        elif strategy.get("strategy_summary"):
            strategy_summary = str(strategy["strategy_summary"]).rstrip("。.")
    if not strategy_summary:
        strategy_summary = optimized_plan_name

    rule_basis = ""
    if strategy:
        if strategy.get("recommended_reason"):
            rule_basis = strategy["recommended_reason"]
        elif strategy.get("rule_basis"):
            rule_basis = str(strategy["rule_basis"]).rstrip("。.")
    if not rule_basis:
        rule_basis = "按规则库检索结果采用安全保守策略"

    lines = [
        "【调度方案】",
        f"采用策略：{strategy_summary}",
        f"最优方案：{plan_name}",
        f"综合评分：{score_pct} / 100",
        f"总晚点：{tdt} min | 影响列车：{affected} 列 | 旅客延误：{tpmd} 人·min",
    ]
    if detail:
        lines.append(detail)
    lines.append(f"依据：{rule_basis}")
    lines.append("新运行图已生成，可在右侧切换查看。")
    return "\n".join(lines)


def process_query(user_query: str, use_llm_strategy: bool = True) -> dict:
    global _latest_adjusted_timetable, _latest_adjustment_meta, _latest_diff_rows

    route = route_query(user_query)
    if route.route == "general_chat":
        return _general_reply(user_query)

    _ensure_knowledge()

    optimizer_context = ""
    optimizer_results: list[dict] = []
    optimized_plan_name = ""
    scenario_result = None
    event = None
    strategy: dict = {}
    retrieved_for_strategy = []
    if route.route == "timetable_optimization" and rag_service.timetable and rag_service.timetable.loaded:
        retrieved_for_strategy = rag_service.retrieval_service.search(user_query, top_k=4)
        if use_llm_strategy:
            strategy = _strategy_from_rules(user_query, retrieved_for_strategy)
        else:
            strategy = {
                "strategy_summary": "快速算法模式，跳过大模型策略生成。",
                "rule_basis": "由本地规则解析与运行图优化器直接生成。",
                "allowed_actions": [],
                "forbidden_actions": [],
                "hard_constraints": ["已通过影响区段的列车不可调整", "必须满足安全间隔"],
                "_llm_skipped": True,
            }
        # 从策略中提取算法动作
        selected_actions = strategy.get("allowed_actions") if strategy.get("allowed_actions") else None
        scenario_result = optimize_for_scenario(
            rag_service.timetable, user_query, strategy=strategy, actions=selected_actions,
        )
        if scenario_result is None and strategy:
            strategy["_fallback_reason"] = "LLM策略未生成可行运行图，已退回本地场景解析与优化。"
            scenario_result = optimize_for_scenario(rag_service.timetable, user_query, strategy=None, actions=None)
        if scenario_result:
            event, optimizer_results, best_plan, adjusted_df = scenario_result
            optimizer_context = format_optimizer_context(event, optimizer_results)
            optimized_plan_name = best_plan.name
            _latest_adjusted_timetable = adjusted_df
            _latest_diff_rows = _compute_timetable_diff(rag_service.timetable.df, adjusted_df)
            _latest_adjustment_meta = {
                "event_type": event.event_type,
                "description": event.description,
                "train_id": event.train_id,
                "station": event.station,
                "delay_minutes": event.delay_minutes,
                "speed_limit": event.speed_limit,
                "start_time": event.start_time,
                "duration_minutes": event.duration_minutes,
                "end_time": event.end_time,
                "range_km": event.range_km,
                "wind_level": event.wind_level,
                "affected_trains": event.affected_trains,
                "excluded_trains": event.excluded_trains[:8],
                "diff_rows": _latest_diff_rows[:20],
                "strategy": strategy,
                "best_plan": best_plan.name,
                "score": optimizer_results[0].get("score", 0) if optimizer_results else 0,
            }

    if optimizer_results:
        result = SimpleNamespace(
            answer="",
            retrieved_chunks=retrieved_for_strategy or rag_service.retrieval_service.search(user_query, top_k=3),
        )
    else:
        try:
            result = rag_service.answer(user_query, extra_timetable_context=optimizer_context)
        except RuntimeError as exc:
            fallback_answer = (
                "本地大模型服务暂不可用，系统先返回算法生成的调度结果。\n\n"
                f"{optimizer_context or '当前问题未识别出可直接优化的运行图扰动。'}\n\n"
                f"LLM错误: {exc}"
            )
            result = SimpleNamespace(
                answer=fallback_answer,
                retrieved_chunks=rag_service.retrieval_service.search(user_query, top_k=3),
            )
    parsed = _parse_answer(result.answer)

    # 构建参考来源
    seen = set()
    references: list[dict] = []
    for chunk in result.retrieved_chunks:
        key = chunk.source_path
        if key not in seen:
            seen.add(key)
            priority_label = (
                "场景流程" if chunk.priority == "scenario"
                else "强规则" if chunk.must_follow
                else "普通规则"
            )
            references.append({
                "title": chunk.title,
                "source": chunk.source_path,
                "priority": priority_label,
            })

    # 运行图评估
    intent = timetable_intent(user_query)
    eval_table = ""
    if intent:
        try:
            plans = []
            # 场景1：单列车晚点
            if intent["train_id"] and intent["delay_minutes"] > 0:
                plans = search_delay_parameter(
                    rag_service.timetable, intent["train_id"], intent["delay_minutes"]
                )
            # 场景2：区间临时限速
            elif intent["speed_limit"] > 0:
                # 从问题中找限速区间
                stations = [s[0] for s in rag_service.timetable.station_pairs]
                match_stn = next((s for s in stations if s != stations[0] and s != stations[-1]), stations[1] if len(stations) > 1 else "")
                plans = generate_speed_restriction_plans(
                    rag_service.timetable, match_stn, intent["speed_limit"]
                )
            if plans:
                eval_results = evaluate_plans(rag_service.timetable, plans)
                eval_table = format_evaluation_table(eval_results)
        except Exception:
            pass

    if optimizer_results:
        # 生成可解释性说明
        detail = ""
        try:
            if scenario_result:
                _event, _results, best_plan, _adj_df = scenario_result
                original = SchedulePlan("original", best_plan.train_ids, best_plan.station_names)
                original.copy_from_original(rag_service.timetable)
                second = optimizer_results[1] if len(optimizer_results) > 1 else None
                detail = explain_best_plan(
                    optimizer_results[0], second, best_plan, original,
                    event_train_id=event.train_id if event else "",
                )
        except Exception:
            pass

        full_answer = _build_concise_dispatch_answer(
            event,
            optimizer_results,
            optimized_plan_name,
            _latest_diff_rows,
            strategy,
            detail=detail,
        )
    else:
        full_answer = parsed["answer"]

    if eval_table and not optimizer_results:
        full_answer += eval_table

    return {
        "answer": full_answer,
        "plan": {
            "title": parsed["plan_title"] or "调度方案",
            "steps": parsed["steps"],
            "note": parsed["note"],
        },
        "references": references,
        "optimizer": {
            "has_adjusted_timetable": bool(optimizer_results),
            "best_plan": optimized_plan_name,
            "metrics": optimizer_results[:3],
            "meta": _latest_adjustment_meta if optimizer_results else {},
            "strategy": strategy if optimizer_results else {},
        },
        "diff": _latest_diff_rows[:20] if optimizer_results else [],
        "route": route.route,
    }


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    if not data or "query" not in data:
        return jsonify({"error": "请求格式错误"}), 400
    use_llm_strategy = bool(data.get("use_llm_strategy", True))
    return jsonify(process_query(data["query"], use_llm_strategy=use_llm_strategy))


@app.route("/health")
def health():
    return jsonify(status="ok")


@app.route("/api/timetable")
def api_timetable():
    import pandas as pd
    version = request.args.get("version", "original")
    xlsx_path = Path(__file__).parent / "planned_timetable.xlsx"
    if not xlsx_path.exists():
        return jsonify({"error": "Timetable file not found"}), 404
    if version == "adjusted":
        if _latest_adjusted_timetable is None:
            return jsonify({"error": "Adjusted timetable not generated yet"}), 404
        df = _latest_adjusted_timetable.fillna("")
    else:
        df = pd.read_excel(xlsx_path, index_col=0).fillna("")
    stations = list(df.columns)
    trains = list(df.index)
    times = [[str(c) if c != "" else "" for c in row] for row in df.values.tolist()]
    return jsonify({
        "stations": stations,
        "trains": trains,
        "times": times,
        "version": version,
        "adjustment": _latest_adjustment_meta if version == "adjusted" else {},
        "diff": _latest_diff_rows if version == "adjusted" else [],
    })


if __name__ == "__main__":
    print("Loading knowledge base...")
    _ensure_knowledge()
    chunk_count = len(rag_service.retrieval_service._chunks)
    print(f"Knowledge loaded: {chunk_count} chunks ready")
    app.run(host="0.0.0.0", port=8000, debug=True, use_reloader=False)

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class QueryRoute:
    route: str
    reason: str


GENERAL_PATTERNS = (
    "你好",
    "您好",
    "hello",
    "hi",
    "你是谁",
    "介绍一下自己",
    "这不对",
    "不对呀",
    "错了",
    "谢谢",
)

OPTIMIZATION_KEYWORDS = (
    "生成新的运行图",
    "生成新运行图",
    "新运行图",
    "调整运行图",
    "优化运行图",
    "限速",
    "晚点",
    "堵门",
    "车门",
    "大风",
    "强风",
    "降雨",
    "暴雨",
    "异物",
    "侵限",
    "故障",
    "扣停",
)

DISPATCH_KEYWORDS = (
    "调度",
    "列车",
    "高铁",
    "动车",
    "车站",
    "区间",
    "接触网",
    "列控",
    "ctc",
    "行车",
    "处置",
    "应急",
)


def route_query(query: str) -> QueryRoute:
    text = query.strip()
    lowered = text.lower()
    compact = "".join(text.split())

    if not compact:
        return QueryRoute("general_chat", "空输入或闲聊")

    if compact in GENERAL_PATTERNS or lowered in GENERAL_PATTERNS:
        return QueryRoute("general_chat", "通用对话")

    if len(compact) <= 8 and any(pattern in compact for pattern in GENERAL_PATTERNS):
        return QueryRoute("general_chat", "短通用对话")

    if any(keyword in compact for keyword in OPTIMIZATION_KEYWORDS):
        return QueryRoute("timetable_optimization", "包含运行图优化或扰动关键词")

    if any(keyword in lowered or keyword in compact for keyword in DISPATCH_KEYWORDS):
        return QueryRoute("dispatch_qa", "铁路调度专业问答")

    return QueryRoute("general_chat", "未命中铁路调度关键词")

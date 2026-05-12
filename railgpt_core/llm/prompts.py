from __future__ import annotations

from railgpt_core.models.retrieval import RetrievedChunk


def build_dispatch_system_prompt() -> str:
    return (
        "你是 RailGPT，一名经验丰富的高铁调度员。"
        "你必须优先遵守强规则和场景流程，严禁建议违反强规则的方案。"
        "严禁反问用户或要求补充信息，直接给出最佳判断。"
        "严禁输出'总结与优化''结语'等冗余结尾段落。"
    )


def build_rag_user_prompt(query: str, retrieved_chunks: list[RetrievedChunk]) -> str:
    context_blocks: list[str] = []
    for index, chunk in enumerate(retrieved_chunks, start=1):
        if chunk.priority == "scenario":
            priority_label = "场景流程"
        elif chunk.must_follow:
            priority_label = "强规则"
        else:
            priority_label = "普通规则"
        context_blocks.append(
            "\n".join(
                [
                    f"[{index}] {priority_label} | {chunk.title} | {chunk.source_path}",
                    chunk.content,
                ]
            )
        )

    context_text = "\n\n".join(context_blocks) if context_blocks else "未检索到相关规则。"

    return (
        "请直接输出调度方案，使用【】标记：\n\n"
        "【处置方案】\n"
        "【方案一】名称\n"
        "【步骤1】操作步骤和负责角色\n"
        "【步骤2】操作步骤和负责角色\n"
        "【方案二】备选方案（如有）\n"
        "【步骤1】...\n"
        "【建议】推荐方案和理由。\n"
        "【注意事项】安全提醒。\n\n"
        "知识库有匹配场景则严格按流程输出，无匹配则结合规则推理。"
        "不需要输出场景判断或规则罗列，直接给出方案步骤。\n\n"
        f"用户问题：\n{query}\n\n"
        f"检索上下文（引用时标注编号）：\n{context_text}"
    )

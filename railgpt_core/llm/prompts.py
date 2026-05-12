from __future__ import annotations

from railgpt_core.models.retrieval import RetrievedChunk


def build_dispatch_system_prompt() -> str:
    return (
        "你是 RailGPT 的铁路调度辅助决策大模型。"
        "你必须优先遵守提供的强规则库内容，任何情况下都不能建议违反强规则的方案。"
        "在满足强规则的前提下，你可以参考普通规则、经验材料和上下文生成可解释的调度建议。"
        "如果用户请求与强规则冲突，你必须明确指出冲突并给出合规替代方案。"
        "回答要结构清晰，优先说明约束、风险、候选方案和建议。"
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
        "请根据以下铁路调度知识上下文回答用户问题。\n\n"
        "要求：\n"
        "1. 先识别并说明相关强规则。\n"
        "2. 不得提出违反强规则的建议。\n"
        "3. 如有多种方案，请给出 2-3 个候选方案并说明取舍。\n"
        "4. 输出尽量面向调度员，语言清晰可执行。\n"
        "5. 请严格按照以下JSON格式输出，不要输出其他内容：\n"
        '{"answer":"总体分析和建议","plan":{"title":"方案标题","steps":["步骤1","步骤2","步骤3"],"note":"注意事项"}}\n\n'
        f"用户问题：\n{query}\n\n"
        f"检索上下文：\n{context_text}"
    )

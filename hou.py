import os
import re
from pathlib import Path

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

app = Flask(__name__)
CORS(app)

rag_service = RAGDispatchService()
_knowledge_loaded = False


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


def process_query(user_query: str) -> dict:
    _ensure_knowledge()

    result = rag_service.answer(user_query)
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

    return {
        "answer": parsed["answer"],
        "plan": {
            "title": parsed["plan_title"] or "调度方案",
            "steps": parsed["steps"],
            "note": parsed["note"],
        },
        "references": references,
    }


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    if not data or "query" not in data:
        return jsonify({"error": "请求格式错误"}), 400
    return jsonify(process_query(data["query"]))


@app.route("/health")
def health():
    return jsonify(status="ok")


if __name__ == "__main__":
    print("Loading knowledge base...")
    _ensure_knowledge()
    chunk_count = len(rag_service.retrieval_service._chunks)
    print(f"Knowledge loaded: {chunk_count} chunks ready")
    app.run(host="0.0.0.0", port=8000, debug=True, use_reloader=False)

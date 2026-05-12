import json
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

# 全局 RAG 服务（首次请求时懒加载知识库）
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


def _parse_llm_json(raw: str) -> dict:
    """尝试从大模型回复中提取 JSON，失败则用纯文本兜底。"""
    # 去除思考块
    text = _strip_thinking(raw)

    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ``` 代码块
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试找到第一个 { 到最后一个 }
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    # 兜底：整体作为 answer
    return {"answer": text, "plan": None}


def process_query(user_query: str) -> dict:
    _ensure_knowledge()

    result = rag_service.answer(user_query)
    parsed = _parse_llm_json(result.answer)

    answer = parsed.get("answer", result.answer)
    plan = parsed.get("plan") or {}

    return {
        "answer": answer,
        "plan": {
            "title": plan.get("title", "调度方案"),
            "steps": plan.get("steps", []),
            "note": plan.get("note", ""),
        },
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

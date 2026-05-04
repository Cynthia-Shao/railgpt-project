# RailGPT Core

`railgpt_core/` 是 RailGPT 项目的共享核心库，供后端服务、测试框架、报告模块共同使用。

## 当前内容

- `models/`：核心数据模型
- `knowledge/`：知识库与多库结构加载
- `retrieval/`：规则切分与最小 Hybrid Retrieval
- `llm/`：本地或云端大模型调用封装
- `utils/`：公共文本工具

## 当前规则库约定

- 强规则库目录：`data/rules/hard_rules/`
- 普通规则库目录：`data/rules/soft_rules/`

强规则属于硬约束，后续大模型生成、优化算法和方案校验都必须优先参考且不得违反。

## 本地大模型配置

当前默认按 OpenAI-compatible 接口接入本地大模型。可通过环境变量配置：

- `RAILGPT_LLM_BASE_URL`
- `RAILGPT_LLM_MODEL`
- `RAILGPT_LLM_API_KEY`

如果未设置 `RAILGPT_LLM_API_KEY`，默认使用 `EMPTY`。

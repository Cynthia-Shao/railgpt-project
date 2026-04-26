# Data Directory

RailGPT 项目的本地数据目录，用于存放规则、调度场景和历史案例等数据文件。

## 目录说明

- `data/rules/`：铁路调度规则、约束、术语、优先级规则等
- `data/scenarios/`：调度场景输入、扰动事件、测试场景等
- `data/cases/`：历史调度案例、人工方案、对比样本等

## 推荐文件格式

- 优先使用：`json`、`jsonl`、`csv`、`md`、`txt`
- 也可以使用：`yaml`

## 建议

- 文件名尽量语义化，例如 `station_rules.json`、`delay_scenario_01.json`
- 如果同一类数据字段风格不一致，先都放进来，后续会统一清洗和接入

# 🛠️ 角色卡调试工作台（workbench）

> 给任意 SillyTavern 角色卡（V2 spec JSON）做「体检 → 压测 → 审查」三段闭环的可复用工具。
> 卡无关（card-agnostic）：工具独立成库（不与任何卡同仓库），卡和探针都是数据。2026-09-06 拍板立项，同日从 CharacterCard 仓库迁出独立。

## 三件套

### ① cardlint.py —— 静态体检（秒级、零成本）
发卡前门禁：V2 spec 必填字段、Lorebook keys 健康（空/重复/蓝灯数）、弯引号规范、超长 description 警告。

```bash
python3 cardlint.py ../character-cards/furina-rolecard/furina_meta.json
```

### ② run_stress.py —— 通用压测 runner（多模型、多回合）
卡无关：探针从代码抽成 JSON 数据（`probes/*.probes.json`），任何卡写一份探针文件即可接入。
自动模拟 SillyTavern 注入：蓝灯（constant）全量常驻 + 绿灯（keys 命中）按回合追加。

```bash
python3 run_stress.py ../furina-rolecard/furina_meta.json probes/furina_meta.probes.json \
    --models z-ai/glm-5.3-flash --out tests/trial.md
```

探针文件格式见 `probes/furina_meta.probes.json`（含 `expect` 预期字段，供人工/审查 agent 比对判定）。
API key 复用 `workspace/.secrets/openrouter-test-o5.key`。

### ③ build_card.py —— 通用构建器（源码→产物，V2 spec）
方法论：JSON 是编译产物，人不该直接编辑 JSON——源码用 md + JSON 混合目录，编译出干净的 V2 卡。

```bash
python3 build_card.py <卡片源码目录> -o ../character-cards/xxx/card.json
```

源码目录：`card.json`（元数据）+ `description.md`（必需）+ personality/scenario/first_mes/mes_example.md（可省）+ `lorebook.json`（可省，条目字段透传）。
已用芙宁娜卡验证：反向提取源码→编译→与原卡 15 字段零差异。

### ④ review/checklist.md —— 审查 agent 提示词清单
深度评审三件套：考据 / 性格 / 机制。沉淀自芙宁娜卡两轮评审闭环。

## 目录

```
workbench/
├── README.md
├── cardlint.py
├── run_stress.py
├── build_card.py    # 通用构建器：源码目录 → V2 JSON
├── probes/          # 探针定义（每卡一份 JSON）
├── review/          # 审查清单
└── tests/           # 压测产物输出
```

## 资产谱系（复用自）
- `furina-rolecard/scripts/meta_stress_test.py` —— 压测框架原型（lorebook 注入模拟 + OpenRouter 重试）
- 芙宁娜卡 V2 spec 实战经验 —— cardlint 检查项来源
- 构建脚本方法论 —— 源码→产物，JSON 是编译产物

## 已知边界
- **lint 警告 ≠ 必须修**：重复 keys 等警告只是让作者知情，是否修由作者拍板（例：元卡「决斗代理人」双条目重复注入是 Luminthalia 拍板的特性——token 廉价，双触发保人物+制度两路内容都到位）。
- run_stress 的 lorebook 注入是简化模拟（无扫描深度/递归/概率触发），复杂世界书行为以实机 SillyTavern 为准
- 思考模型必须给足 max_tokens（≥8000），否则思考链吃光配额正文为空，会误判模型「废了」（2026-08-10 教训）
- 压测结论要固定 provider 才可复现（OpenRouter 随机路由会吃掉结论）

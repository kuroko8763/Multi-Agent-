# Architecture Review Agent - Multi-Agent Code Review System

基于 Multi-Agent 协作的企业级架构合规自动审判系统。

## 系统架构

```
PR Understanding Agent → Architecture Rule Agent → Impact Assessment Agent → Review Opinion Agent → Regression Advice Agent
         ↓                      ↓                        ↓                        ↓                        ↓
      解析PR上下文          扫描违规模式             评估影响范围             生成评审意见             制定测试计划
```

## 五大Agent职责

| Agent | 职责 | 输出 |
|-------|------|------|
| **PR Understanding Agent** | 解析PR变更内容、关联上下文、识别意图和风险 | PRContext |
| **Architecture Rule Agent** | 基于预定义规则扫描代码，识别违规模式 | RuleCheckResult |
| **Impact Assessment Agent** | 构造调用链路图，评估改动对上下游的影响 | ImpactAssessmentResult |
| **Review Opinion Agent** | 综合所有输出，生成结构化评审意见 | ReviewSummary |
| **Regression Advice Agent** | 根据风险等级推荐测试用例子集 | RegressionTestPlan |

## 核心特性

- **长链推理**: 5个Agent流水线式协作，每个Agent专注单一职责
- **架构规范检查**: 内置20+条规则，覆盖安全、质量、性能、测试等
- **影响评估**: 自动识别上下游依赖，评估级联风险
- **Breaking Change检测**: 提前发现API签名、数据库Schema等变更风险
- **智能测试计划**: 根据风险等级生成针对性回归测试建议

## 项目结构

```
arch_review_agent/
├── agents/
│   ├── __init__.py
│   ├── pr_analyzer.py         # PR理解Agent
│   ├── rule_checker.py         # 架构规则Agent
│   ├── impact_evaluator.py     # 影响评估Agent
│   ├── review_generator.py     # 评审生成Agent
│   └── regression_planner.py   # 回归测试Agent
├── tests/
│   └── test_agents.py          # 单元测试
├── rules/                      # 自定义规则目录（可选）
├── reports/                    # 生成的报告输出目录
├── pipeline.py                 # 主流水线
├── main.py                     # CLI入口
├── requirements.txt
└── README.md
```

## 安装

```bash
pip install -r requirements.txt
```

## 使用方法

### 快速演示

```bash
python main.py demo
```

### 审查PR

```bash
python main.py run --pr-data pr.json --code-dir ./src --output report.md
```

### 生成CI配置

```bash
python main.py generate-ci --output .github/workflows/review.yml
```

### 运行测试

```bash
python main.py test
```

## 示例输出

```
================================================================================
🏛️  Architecture Review Pipeline
================================================================================
PR #1234: feat: 添加支付网关集成与交易记录模块
Author: zhangsan
--------------------------------------------------------------------------------
[1/5] 🔍 PR Understanding Agent...
  ✅ Intent: feature
  ✅ Domain: backend
  ✅ Files: 6 changed
  ✅ Risks: 2 identified
  ⏱️  45ms

[2/5] 📜 Architecture Rule Agent...
  ✅ Rules checked: 20
  ✅ Triggered: 3
  ✅ Violations: 5
  ✅ Compliance score: 65.0
  🔴 Critical: 2
  ⏱️  120ms

[3/5] 📊 Impact Assessment Agent...
  ✅ Impacted services: 2
  ✅ Impacted modules: 4
  ✅ Cascade risk: MEDIUM
  ✅ Rollback complexity: HIGH
  ✅ Test coverage: 40%
  🚨 Breaking changes: 1
  ⏱️  85ms

[4/5] 📝 Review Opinion Agent...
  ✅ Overall score: 58.5/100
  ✅ Approval status: CONDITIONAL
  ✅ Comments: 7
  ✅ Must fix: 3
  ✅ Should fix: 4
  ⏱️  60ms

[5/5] 🧪 Regression Advice Agent...
  ✅ Total tests: 6
  ✅ Critical: 3
  ✅ Estimated time: ~25分钟
  ⏱️  30ms

================================================================================
✅ Pipeline completed in 340ms
================================================================================
```

## 合规评分标准

| 评分 | 状态 | 说明 |
|------|------|------|
| 70-100 | ✅ Approved | 符合标准，可以合并 |
| 50-69 | ⚠️ Conditional | 需处理Must Fix后合并 |
| 0-49 | ❌ Rejected | 存在严重问题，需重大修改 |

## 内置规则

| 规则ID | 名称 | 严重性 |
|--------|------|--------|
| SEC001 | No Hardcoded Credentials | Critical |
| SEC002 | No SQL Injection Risk | Critical |
| SEC003 | No Eval/Exec Usage | Major |
| ARCH001 | No Cyclic Dependencies | Critical |
| ARCH002 | Layer Violation - DB Access in UI | Major |
| PERF001 | No N+1 Query Problem | Major |
| TEST001 | Critical Code Without Tests | Major |
| DEPLOY001 | No Secret in Git | Critical |

## License

MIT
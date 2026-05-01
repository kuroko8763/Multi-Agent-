"""
Multi-Agent Architecture Review Pipeline

演示如何将5个Agent串联成长链推理流水线:
PR理解Agent → 架构规范Agent → 影响评估Agent → 评审意见Agent → 回归建议Agent

每个Agent接收上一阶段的输出，形成完整的审查闭环
"""

import json
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from agents import (
    PRUnderstandingAgent,
    ArchitectureRuleAgent,
    ImpactAssessmentAgent,
    ReviewOpinionAgent,
    RegressionAdviceAgent
)
from agents.pr_analyzer import PRContext, FileChange
from agents.rule_checker import RuleCheckResult
from agents.impact_evaluator import ImpactAssessmentResult
from agents.review_generator import ReviewSummary
from agents.regression_planner import RegressionTestPlan


@dataclass
class PipelineConfig:
    """流水线配置"""
    enable_ml_prioritization: bool = True
    min_approval_score: float = 70.0
    require_critical_approval: bool = True
    auto_assign_reviewers: bool = True


@dataclass
class PipelineResult:
    """流水线完整输出"""
    pr_context: Dict
    rule_result: Dict
    impact_result: Dict
    review_summary: Dict
    test_plan: Dict
    execution_time: float
    pipeline_version: str = "1.0.0"


class ArchitectureReviewPipeline:
    """
    架构合规自动审判系统 - 主流水线

    使用方式:
        pipeline = ArchitectureReviewPipeline(config)
        result = pipeline.run(pr_data, code_contents)
        
        # 查看评审结果
        print(result.review_summary.summary)
        
        # 生成报告
        print(pipeline.generate_full_report(result))
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()
        
        # 初始化所有Agent
        self.pr_agent = PRUnderstandingAgent()
        self.rule_agent = ArchitectureRuleAgent(
            rules_dir='rules'  # 可扩展的自定义规则目录
        )
        self.impact_agent = ImpactAssessmentAgent()
        self.review_agent = ReviewOpinionAgent()
        self.regression_agent = RegressionAdviceAgent()
        
        # 执行统计
        self.stats = {
            'total_runs': 0,
            'total_time': 0,
            'avg_score': 0
        }

    def run(self, pr_data: Dict, code_contents: Optional[Dict[str, str]] = None) -> PipelineResult:
        """
        执行完整的审查流水线
        
        Args:
            pr_data: PR数据，格式见 pr_analyzer.py 中的 PRContext
            code_contents: 文件路径到代码内容的映射，用于深度检查
            
        Returns:
            PipelineResult: 包含所有阶段的完整输出
        """
        start_time = time.time()
        code_contents = code_contents or {}
        
        print("=" * 60)
        print("🏛️  Architecture Review Pipeline")
        print("=" * 60)
        print(f"PR #{pr_data.get('pr_number', '?')}: {pr_data.get('title', 'No title')}")
        print(f"Author: {pr_data.get('author', 'Unknown')}")
        print("-" * 60)

        # ==================== Stage 1: PR Understanding ====================
        print("\n[1/5] 🔍 PR Understanding Agent...")
        stage_start = time.time()
        pr_context = self.pr_agent.analyze(pr_data)
        print(f"  ✅ Intent: {pr_context.intent_summary}")
        print(f"  ✅ Domain: {pr_context.technical_domain}")
        print(f"  ✅ Files: {pr_context.overall_stats.get('total_files', 0)} changed")
        print(f"  ✅ Risks: {len(pr_context.risk_factors)} identified")
        print(f"  ⏱️  {(time.time() - stage_start)*1000:.0f}ms")

        # ==================== Stage 2: Rule Checking ====================
        print("\n[2/5] 📜 Architecture Rule Agent...")
        stage_start = time.time()
        rule_result = self.rule_agent.check(pr_context, code_contents)
        print(f"  ✅ Rules checked: {rule_result.total_rules_checked}")
        print(f"  ✅ Triggered: {rule_result.rules_triggered}")
        print(f"  ✅ Violations: {len(rule_result.violations)}")
        print(f"  ✅ Compliance score: {rule_result.compliance_score:.1f}")
        if rule_result.critical_issues:
            print(f"  🔴 Critical: {len(rule_result.critical_issues)}")
        print(f"  ⏱️  {(time.time() - stage_start)*1000:.0f}ms")

        # ==================== Stage 3: Impact Assessment ====================
        print("\n[3/5] 📊 Impact Assessment Agent...")
        stage_start = time.time()
        impact_result = self.impact_agent.assess(pr_context, code_contents)
        print(f"  ✅ Impacted services: {len(impact_result.impacted_services)}")
        print(f"  ✅ Impacted modules: {len(impact_result.impacted_modules)}")
        print(f"  ✅ Cascade risk: {impact_result.cascade_risk.upper()}")
        print(f"  ✅ Rollback complexity: {impact_result.rollback_complexity.upper()}")
        print(f"  ✅ Test coverage: {impact_result.tested_surface:.0%}")
        if impact_result.breaking_changes:
            print(f"  🚨 Breaking changes: {len(impact_result.breaking_changes)}")
        print(f"  ⏱️  {(time.time() - stage_start)*1000:.0f}ms")

        # ==================== Stage 4: Review Generation ====================
        print("\n[4/5] 📝 Review Opinion Agent...")
        stage_start = time.time()
        review_summary = self.review_agent.generate(pr_context, rule_result, impact_result)
        print(f"  ✅ Overall score: {review_summary.overall_score}/100")
        print(f"  ✅ Approval status: {review_summary.approval_status.upper()}")
        print(f"  ✅ Comments: {len(review_summary.comments)}")
        print(f"  ✅ Must fix: {len(review_summary.must_fix)}")
        print(f"  ✅ Should fix: {len(review_summary.should_fix)}")
        print(f"  ⏱️  {(time.time() - stage_start)*1000:.0f}ms")

        # ==================== Stage 5: Regression Advice ====================
        print("\n[5/5] 🧪 Regression Advice Agent...")
        stage_start = time.time()
        test_plan = self.regression_agent.generate_plan(pr_context, impact_result, rule_result)
        print(f"  ✅ Total tests: {test_plan.total_tests}")
        print(f"  ✅ Critical: {test_plan.critical_tests}")
        print(f"  ✅ Estimated time: {test_plan.estimated_duration}")
        if test_plan.coverage_gaps:
            print(f"  ⚠️  Coverage gaps: {len(test_plan.coverage_gaps)}")
        print(f"  ⏱️  {(time.time() - stage_start)*1000:.0f}ms")

        # ==================== Complete ====================
        execution_time = time.time() - start_time
        print("\n" + "=" * 60)
        print(f"✅ Pipeline completed in {execution_time*1000:.0f}ms")
        print("=" * 60)

        # 更新统计
        self._update_stats(execution_time, review_summary.overall_score)

        return PipelineResult(
            pr_context=asdict(pr_context),
            rule_result=asdict(rule_result),
            impact_result=asdict(impact_result),
            review_summary=asdict(review_summary),
            test_plan=asdict(test_plan),
            execution_time=execution_time
        )

    def generate_full_report(self, result: PipelineResult) -> str:
        """生成完整的Markdown审查报告"""
        lines = [
            "# 🏛️ Architecture Compliance Review Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Pipeline:** v{result.pipeline_version}",
            f"**Execution Time:** {result.execution_time*1000:.0f}ms",
            "",
            "---",
            ""
        ]

        # PR Summary
        pr = result.pr_context
        lines.extend([
            "## 📋 PR Summary",
            "",
            f"**PR #{pr['pr_number']}:** {pr['title']}",
            f"**Author:** {pr['author']} | **Domain:** {pr['technical_domain']}",
            f"**Intent:** {pr['intent_summary']}",
            "",
            f"- Files: {pr['overall_stats'].get('total_files', 0)}",
            f"- Changes: +{pr['overall_stats'].get('total_additions', 0)} / -{pr['overall_stats'].get('total_deletions', 0)}",
            f"- Languages: {', '.join(pr['overall_stats'].get('language_distribution', {}).keys())}",
            ""
        ])

        # Review Summary
        review = result.review_summary
        status_icons = {'approved': '✅', 'conditional': '⚠️', 'rejected': '❌'}
        lines.extend([
            "## 📊 Review Summary",
            "",
            f"{status_icons.get(review['approval_status'], '❓')} **Status:** {review['approval_status'].upper()}",
            f"**Score:** {review['overall_score']}/100",
            f"",
            review['summary'].replace('\n', '  \n'),
            ""
        ])

        # Must Fix
        if review['must_fix']:
            lines.extend([
                "## 🚨 Must Fix",
                ""
            ])
            for item in review['must_fix']:
                lines.append(f"- {item}")
            lines.append("")

        # Should Fix
        if review['should_fix']:
            lines.extend([
                "## ⚠️ Should Fix",
                ""
            ])
            for item in review['should_fix']:
                lines.append(f"- {item}")
            lines.append("")

        # Nit Picks
        if review['nit_picks']:
            lines.extend([
                "## 💡 Nit Picks",
                ""
            ])
            for item in review['nit_picks']:
                lines.append(f"- {item}")
            lines.append("")

        # Rule Violations
        rule = result.rule_result
        if rule['violations']:
            lines.extend([
                "## 📜 Rule Violations",
                "",
                f"**Compliance Score:** {rule['compliance_score']:.1f}/100",
                ""
            ])
            
            if rule['critical_issues']:
                lines.append("### 🔴 Critical")
                for v in rule['critical_issues'][:5]:
                    lines.append(f"- **{v['rule_name']}** at `{v['file_path']}`")
                    if v['line_number']:
                        lines.append(f"  - Line {v['line_number']}: {v['description']}")
                lines.append("")
            
            if rule['warning_issues']:
                lines.append("### 🟡 Warnings")
                for v in rule['warning_issues'][:10]:
                    lines.append(f"- **{v['rule_name']}** at `{v['file_path']}`")
                lines.append("")

        # Impact Assessment
        impact = result.impact_result
        lines.extend([
            "## 📊 Impact Assessment",
            "",
            f"- **Cascade Risk:** {impact['cascade_risk'].upper()}",
            f"- **Rollback Complexity:** {impact['rollback_complexity'].upper()}",
            f"- **Test Coverage:** {impact['tested_surface']:.0%}",
            ""
        ])
        
        if impact['breaking_changes']:
            lines.append("### 🚨 Breaking Changes")
            for b in impact['breaking_changes']:
                lines.append(f"- [{b['severity'].upper()}] {b['type']} in `{b['file']}`")
            lines.append("")

        if impact['recommendations']:
            lines.append("### 📋 Recommendations")
            for r in impact['recommendations']:
                lines.append(f"- {r}")
            lines.append("")

        # Test Plan
        test_plan = result.test_plan
        lines.extend([
            "## 🧪 Regression Test Plan",
            "",
            f"**Total Tests:** {test_plan['total_tests']}",
            f"**Critical:** {test_plan['critical_tests']}",
            f"**Estimated Duration:** {test_plan['estimated_duration']}",
            ""
        ])
        
        if test_plan['recommendations']:
            lines.append("### Recommended Tests")
            for rec in test_plan['recommendations'][:10]:
                priority_icon = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'}
                icon = priority_icon.get(rec['priority'], '•')
                lines.append(f"{icon} **{rec['test_type'].upper()}** - {rec['description']}")
                lines.append(f"   Target: `{'`, `'.join(rec['target_modules'][:2])}`")
            lines.append("")

        if test_plan['coverage_gaps']:
            lines.append("### ⚠️ Coverage Gaps")
            for gap in test_plan['coverage_gaps']:
                lines.append(f"- {gap}")
            lines.append("")

        lines.extend([
            "---",
            "",
            "*Report generated by Multi-Agent Architecture Review Pipeline*"
        ])

        return '\n'.join(lines)

    def _update_stats(self, execution_time: float, score: float):
        """更新流水线统计"""
        self.stats['total_runs'] += 1
        self.stats['total_time'] += execution_time
        self.stats['avg_score'] = (
            (self.stats['avg_score'] * (self.stats['total_runs'] - 1) + score)
            / self.stats['total_runs']
        )

    def get_stats(self) -> Dict:
        """获取流水线统计信息"""
        return {
            **self.stats,
            'avg_score': round(self.stats['avg_score'], 1)
        }

    def export_json(self, result: PipelineResult, output_path: str):
        """导出JSON格式结果"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(result), f, ensure_ascii=False, indent=2, default=str)

    def export_report(self, result: PipelineResult, output_path: str):
        """导出Markdown格式报告"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(self.generate_full_report(result))


# ==================== Demo & Entry Point ====================

def create_sample_pr_data() -> Dict:
    """创建示例PR数据用于演示"""
    return {
        'pr_number': 1234,
        'title': 'feat: 添加支付网关集成与交易记录模块',
        'description': '''
实现新的支付网关集成，支持微信、支付宝和信用卡支付。

主要变更:
- 新增 PaymentGateway 服务
- 新增 TransactionRecord 数据模型
- 添加相关单元测试
- 更新配置文件
        ''',
        'author': 'zhangsan',
        'base_branch': 'main',
        'head_branch': 'feature/payment-gateway',
        'created_at': '2026-05-01T10:30:00',
        'files': [
            {
                'path': 'src/services/payment_gateway.py',
                'status': 'added',
                'diff': '''+class PaymentGateway:
+    def __init__(self, api_key, merchant_id):
+        self.api_key = api_key
+        self.merchant_id = merchant_id
+        self.base_url = "https://api.payment.com"
+    
+    def charge(self, amount, currency='CNY'):
+        if amount <= 0:
+            raise ValueError("Amount must be positive")
+        
+        # TODO: implement actual API call
+        return {"status": "success", "transaction_id": "tx123"}
+    
+    def refund(self, transaction_id, amount):
+        # TODO: implement refund logic
+        return {"status": "refunded"}'''
            },
            {
                'path': 'src/models/transaction.py',
                'status': 'added',
                'diff': '''+class TransactionRecord:
+    id: str
+    amount: Decimal
+    currency: str
+    payment_method: str
+    status: str
+    created_at: datetime
+    
+    def save(self):
+        # Direct DB access in model layer - ARCH violation!
+        db.execute("INSERT INTO transactions ...")'''
            },
            {
                'path': 'src/services/auth.py',
                'status': 'modified',
                'diff': '''     def verify_token(self, token):
-        if not token:
-            return False
+        # Hardcoded secret - security issue!
+        if token == "debug_secret_12345":
+            return True
+        if not token:
+            return False
         return self.jwt.decode(token, "secret_key", algorithms=["HS256"])'''
            },
            {
                'path': 'tests/test_payment.py',
                'status': 'added',
                'diff': '''+def test_charge_success():
+    gateway = PaymentGateway("test_key", "test_merchant")
+    result = gateway.charge(100)
+    assert result["status"] == "success")'''
            },
            {
                'path': 'config/payment.yaml',
                'status': 'added',
                'diff': '''+payment:
+  api_key: "sk_live_123456789"  # This is a SECRET!
+  merchant_id: "M12345"
+  webhook_url: "https://example.com/webhook"
+  timeout: 30'''
            },
            {
                'path': 'migrations/001_add_transactions.sql',
                'status': 'added',
                'diff': '''+CREATE TABLE transactions (
+    id SERIAL PRIMARY KEY,
+    amount DECIMAL NOT NULL,
+    currency VARCHAR(3),
+    created_at TIMESTAMP DEFAULT NOW()
+);'''
            }
        ],
        'commits': [
            {
                'hash': 'abc123def456',
                'author': 'zhangsan',
                'message': 'feat: add payment gateway skeleton',
                'date': '2026-05-01T09:00:00',
                'files': ['src/services/payment_gateway.py']
            },
            {
                'hash': 'def789ghi012',
                'author': 'zhangsan',
                'message': 'fix: add amount validation',
                'date': '2026-05-01T10:00:00',
                'files': ['src/services/payment_gateway.py']
            }
        ],
        'linked_issues': [
            {
                'id': '1234',
                'title': '集成支付网关',
                'status': 'in_progress',
                'priority': 'high',
                'labels': ['feature', 'payment']
            }
        ]
    }


def main():
    """演示入口"""
    print("\n🚀 Multi-Agent Architecture Review Pipeline Demo")
    print("=" * 60)
    
    # 创建示例PR数据
    pr_data = create_sample_pr_data()
    
    # 模拟代码内容（实际使用时应从仓库获取）
    code_contents = {
        'src/services/payment_gateway.py': open('src/services/payment_gateway.py').read() if Path('src/services/payment_gateway.py').exists() else pr_data['files'][0]['diff'],
        'src/models/transaction.py': pr_data['files'][1]['diff'],
        'src/services/auth.py': pr_data['files'][2]['diff'],
        'config/payment.yaml': pr_data['files'][4]['diff']
    }
    
    # 初始化流水线
    pipeline = ArchitectureReviewPipeline()
    
    # 执行审查
    result = pipeline.run(pr_data, code_contents)
    
    # 打印报告
    print("\n" + "=" * 60)
    print("📄 FULL REPORT")
    print("=" * 60)
    print(pipeline.generate_full_report(result))
    
    # 可选：导出结果
    output_dir = Path('reports')
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    pipeline.export_json(result, f'reports/review_{timestamp}.json')
    pipeline.export_report(result, f'reports/review_{timestamp}.md')
    
    print(f"\n📁 Reports saved to reports/review_{timestamp}.json|md")
    print(f"📊 Pipeline stats: {pipeline.get_stats()}")


if __name__ == '__main__':
    main()
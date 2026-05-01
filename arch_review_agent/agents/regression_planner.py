"""
Regression Advice Agent
负责根据风险等级推荐需要的测试用例子集
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple, Any
from pathlib import Path

from .pr_analyzer import PRContext
from .impact_evaluator import ImpactAssessmentResult
from .rule_checker import RuleCheckResult


@dataclass
class TestRecommendation:
    """测试推荐项"""
    test_type: str  # unit, integration, e2e, performance, security
    priority: str  # critical, high, medium, low
    description: str
    target_modules: List[str]
    estimated_duration: str  # 预估执行时间
    required: bool  # 是否为必须项


@dataclass
class RegressionTestPlan:
    """回归测试计划"""
    total_tests: int
    critical_tests: int
    estimated_duration: str  # 总预估时间
    recommendations: List[TestRecommendation] = field(default_factory=list)
    skipped_modules: List[str] = field(default_factory=list)  # 可以跳过的模块
    coverage_gaps: List[str] = field(default_factory=list)


@dataclass
class RiskContext:
    """风险上下文"""
    cascade_risk: str
    rollback_complexity: str
    breaking_changes: List[Dict]
    compliance_score: float
    untested_surface: List[str]


class RegressionAdviceAgent:
    """
    回归建议Agent：根据PR风险等级，生成针对性测试计划
    """

    # 测试类型映射
    TEST_TYPES = {
        'unit': {
            'description': '单元测试',
            'execution_time_per_test': '~30秒',
            'coverage_focus': '代码逻辑分支'
        },
        'integration': {
            'description': '集成测试',
            'execution_time_per_test': '~2分钟',
            'coverage_focus': '模块间交互'
        },
        'e2e': {
            'description': '端到端测试',
            'execution_time_per_test': '~10分钟',
            'coverage_focus': '用户场景覆盖'
        },
        'performance': {
            'description': '性能测试',
            'execution_time_per_test': '~15分钟',
            'coverage_focus': '响应时间/吞吐量'
        },
        'security': {
            'description': '安全扫描',
            'execution_time_per_test': '~5分钟',
            'coverage_focus': '漏洞/注入检测'
        }
    }

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.base_ci_path = self.config.get('ci_path', '.github/workflows')

    def generate_plan(self, pr_context: PRContext,
                      impact_result: ImpactAssessmentResult,
                      rule_result: RuleCheckResult) -> RegressionTestPlan:
        """
        生成回归测试计划
        """
        risk_context = RiskContext(
            cascade_risk=impact_result.cascade_risk,
            rollback_complexity=impact_result.rollback_complexity,
            breaking_changes=impact_result.breaking_changes,
            compliance_score=rule_result.compliance_score,
            untested_surface=impact_result.untested_surface
        )

        recommendations: List[TestRecommendation] = []
        skipped_modules: List[str] = []
        coverage_gaps: List[str] = []

        # 1. 根据风险等级确定测试策略
        test_intensity = self._determine_test_intensity(risk_context)

        # 2. 生成基础测试推荐
        base_recommendations = self._generate_base_recommendations(
            pr_context, risk_context, test_intensity
        )
        recommendations.extend(base_recommendations)

        # 3. 针对Breaking Changes添加特定测试
        breaking_recommendations = self._generate_breaking_change_tests(
            impact_result.breaking_changes
        )
        recommendations.extend(breaking_recommendations)

        # 4. 针对违规添加特定测试
        violation_recommendations = self._generate_violation_tests(rule_result)
        recommendations.extend(violation_recommendations)

        # 5. 确定可以跳过的模块
        skipped_modules = self._determine_skippable_modules(
            pr_context, impact_result
        )

        # 6. 识别测试覆盖缺口
        coverage_gaps = self._identify_coverage_gaps(
            pr_context, impact_result, recommendations
        )

        # 计算统计
        total_tests = len(recommendations)
        critical_tests = sum(1 for r in recommendations if r.priority == 'critical')

        # 计算总预估时间
        total_duration = self._estimate_total_duration(recommendations)

        return RegressionTestPlan(
            total_tests=total_tests,
            critical_tests=critical_tests,
            estimated_duration=total_duration,
            recommendations=recommendations,
            skipped_modules=skipped_modules,
            coverage_gaps=coverage_gaps
        )

    def _determine_test_intensity(self, risk_context: RiskContext) -> str:
        """根据风险等级确定测试强度"""
        score = 0

        # Cascade risk
        if risk_context.cascade_risk == 'high':
            score += 3
        elif risk_context.cascade_risk == 'medium':
            score += 2
        else:
            score += 1

        # Rollback complexity
        if risk_context.rollback_complexity == 'high':
            score += 2
        elif risk_context.rollback_complexity == 'medium':
            score += 1

        # Breaking changes
        score += len(risk_context.breaking_changes) * 2

        # Compliance score
        if risk_context.compliance_score < 70:
            score += 2
        elif risk_context.compliance_score < 90:
            score += 1

        # Untested surface
        if len(risk_context.untested_surface) > 10:
            score += 2
        elif len(risk_context.untested_surface) > 5:
            score += 1

        if score >= 8:
            return 'exhaustive'  # 全面测试
        elif score >= 5:
            return 'standard'  # 标准测试
        elif score >= 3:
            return 'minimal'  # 最小测试
        else:
            return 'baseline'  # 基础测试

    def _generate_base_recommendations(self, pr_context: PRContext,
                                        risk_context: RiskContext,
                                        intensity: str) -> List[TestRecommendation]:
        """生成基础测试推荐"""
        recommendations = []
        changed_files = pr_context.changed_files
        stats = pr_context.overall_stats

        # 单元测试推荐（所有变更都应有）
        if intensity in ['exhaustive', 'standard']:
            recommendations.append(TestRecommendation(
                test_type='unit',
                priority='high',
                description='为所有新增和修改的核心函数编写单元测试',
                target_modules=[f.file_path for f in changed_files[:10]],
                estimated_duration=f'~{len(changed_files) * 2}分钟',
                required=intensity == 'exhaustive'
            ))
        elif intensity == 'minimal':
            # 只测试关键文件
            critical = [f for f in changed_files if not f.is_test and not f.is_documentation]
            recommendations.append(TestRecommendation(
                test_type='unit',
                priority='medium',
                description='为修改的核心业务逻辑编写单元测试',
                target_modules=[f.file_path for f in critical[:5]],
                estimated_duration='~5分钟',
                required=False
            ))

        # 集成测试推荐
        if intensity in ['exhaustive', 'standard'] or risk_context.cascade_risk == 'high':
            affected_modules = list(set(
                f.file_path.split('/')[0] if '/' in f.file_path else f.file_path
                for f in changed_files
            ))
            
            recommendations.append(TestRecommendation(
                test_type='integration',
                priority='high' if risk_context.cascade_risk == 'high' else 'medium',
                description=f'验证 {len(affected_modules)} 个模块间的交互正确性',
                target_modules=affected_modules[:5],
                estimated_duration='~10分钟',
                required=intensity == 'exhaustive'
            ))

        # E2E测试推荐
        if intensity == 'exhaustive' or risk_context.breaking_changes:
            recommendations.append(TestRecommendation(
                test_type='e2e',
                priority='medium',
                description='验证关键用户场景的端到端流程',
                target_modules=['主要业务流'],
                estimated_duration='~20分钟',
                required=False
            ))

        # 性能测试推荐
        large_change_threshold = 500  # 变更行数
        if stats.get('total_lines_changed', 0) > large_change_threshold:
            recommendations.append(TestRecommendation(
                test_type='performance',
                priority='medium',
                description='验证变更不会导致性能退化',
                target_modules=[f.file_path for f in changed_files if not f.is_test][:3],
                estimated_duration='~15分钟',
                required=False
            ))

        # 安全测试推荐
        if any(v.severity == 'critical' for v in rule_result.critical_issues if 'rule_result' in dir()):
            pass

        return recommendations

    def _generate_breaking_change_tests(self, breaking_changes: List[Dict]) -> List[TestRecommendation]:
        """针对Breaking Changes生成测试推荐"""
        recommendations = []

        for change in breaking_changes:
            change_type = change.get('type', 'unknown')
            
            if change_type == 'api_signature':
                recommendations.append(TestRecommendation(
                    test_type='integration',
                    priority='critical',
                    description=f'验证API签名变更的兼容性',
                    target_modules=[change['file']],
                    estimated_duration='~5分钟',
                    required=True
                ))
                recommendations.append(TestRecommendation(
                    test_type='e2e',
                    priority='high',
                    description='验证API消费者是否需要适配',
                    target_modules=['API依赖方'],
                    estimated_duration='~10分钟',
                    required=False
                ))
            
            elif change_type == 'database_schema':
                recommendations.append(TestRecommendation(
                    test_type='integration',
                    priority='critical',
                    description='验证数据库迁移的正向和回滚',
                    target_modules=[change['file']],
                    estimated_duration='~15分钟',
                    required=True
                ))
            
            elif change_type == 'data_contract':
                recommendations.append(TestRecommendation(
                    test_type='unit',
                    priority='high',
                    description='验证数据结构变更的序列化/反序列化',
                    target_modules=[change['file']],
                    estimated_duration='~5分钟',
                    required=True
                ))

        return recommendations

    def _generate_violation_tests(self, rule_result: RuleCheckResult) -> List[TestRecommendation]:
        """针对规则违规生成测试推荐"""
        recommendations = []

        # 按规则类型生成针对性测试
        sec_violations = [v for v in rule_result.critical_issues if v.rule_id.startswith('SEC')]
        if sec_violations:
            recommendations.append(TestRecommendation(
                test_type='security',
                priority='critical',
                description='安全扫描：验证所有安全相关修复',
                target_modules=[v.file_path for v in sec_violations],
                estimated_duration='~10分钟',
                required=True
            ))

        perf_violations = [v for v in rule_result.warning_issues if v.rule_id.startswith('PERF')]
        if perf_violations:
            recommendations.append(TestRecommendation(
                test_type='performance',
                priority='medium',
                description='性能测试：验证无N+1查询等问题',
                target_modules=[v.file_path for v in perf_violations[:3]],
                estimated_duration='~10分钟',
                required=False
            ))

        return recommendations

    def _determine_skippable_modules(self, pr_context: PRContext,
                                       impact_result: ImpactAssessmentResult) -> List[str]:
        """确定可以跳过的测试模块"""
        skipped = []

        for file_change in pr_context.changed_files:
            # 文档变更
            if file_change.is_documentation:
                skipped.append(f"{file_change.file_path} (文档变更，可跳过)")
            
            # 配置变更（如果影响范围小）
            elif file_change.is_config:
                if file_change.change_type == 'added':
                    skipped.append(f"{file_change.file_path} (新增配置，无需测试)")

        # 测试覆盖率已足够的地方
        if impact_result.tested_surface > 0.8:
            for module in impact_result.untested_surface[:3]:
                skipped.append(f"{module} (测试覆盖充分)")

        return skipped

    def _identify_coverage_gaps(self, pr_context: PRContext,
                                impact_result: ImpactAssessmentResult,
                                recommendations: List[TestRecommendation]) -> List[str]:
        """识别测试覆盖缺口"""
        gaps = []

        # 关键路径未被测试
        critical_modules = ['auth', 'payment', 'core', 'transaction']
        for cm in critical_modules:
            affected = [f.file_path for f in pr_context.changed_files if cm in f.file_path.lower()]
            if affected:
                has_test = any(
                    cm in str(rec.target_modules) 
                    for rec in recommendations 
                    if rec.test_type in ['unit', 'integration']
                )
                if not has_test:
                    gaps.append(f"关键模块 {cm} 缺少测试覆盖")

        # 未测试的下游影响
        for module in impact_result.untested_surface[:5]:
            has_recommendation = any(
                module in str(rec.target_modules) 
                for rec in recommendations
            )
            if not has_recommendation:
                gaps.append(f"受影响模块 `{module}` 建议补充测试")

        return gaps

    def _estimate_total_duration(self, recommendations: List[TestRecommendation]) -> str:
        """估算总执行时间"""
        time_map = {
            'unit': 2,  # 分钟
            'integration': 5,
            'e2e': 10,
            'performance': 15,
            'security': 5
        }

        total = sum(time_map.get(r.test_type, 5) for r in recommendations)
        
        if total < 60:
            return f"~{total}分钟"
        else:
            hours = total // 60
            mins = total % 60
            return f"~{hours}小时{mins}分钟" if mins > 0 else f"~{hours}小时"

    def generate_ci_config(self, plan: RegressionTestPlan, intensity: str = 'standard') -> str:
        """
        生成CI配置文件（GitHub Actions格式）
        """
        test_jobs = []
        
        for rec in plan.recommendations:
            if rec.priority in ['critical', 'high'] or intensity == 'exhaustive':
                test_jobs.append(self._generate_job_for_recommendation(rec))
        
        jobs_yaml = '\n'.join(test_jobs)
        
        return f"""name: Regression Tests

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  analyze:
    runs-on: ubuntu-latest
    outputs:
      test-plan: ${{{{ steps.plan.outputs.plan }}}}
    steps:
      - uses: actions/checkout@v4
      - name: Generate test plan
        id: plan
        run: |
          echo 'plan=${{{{ toJson(plan) }}}}' >> $GITHUB_OUTPUT

  regression-tests:
    needs: analyze
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        test-type: [unit, integration, e2e]
    steps:
      - uses: actions/checkout@v4
      - name: Run ${{{{ matrix.test-type }}}} tests
        run: |
          # 实际命令根据项目情况调整
          pytest tests/${{{{ matrix.test-type }}}/ --tb=short

  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Security scan
        run: |
          # 安全扫描命令
          bandit -r src/

  deploy-staging:
    needs: [regression-tests, security-scan]
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to staging
        run: |
          echo "部署到staging环境..."
"""

    def generate_report(self, plan: RegressionTestPlan) -> str:
        """生成测试计划报告"""
        lines = [
            "## 回归测试计划",
            "",
            f"**总测试项:** {plan.total_tests}",
            f"**关键测试:** {plan.critical_tests}",
            f"**预估执行时间:** {plan.estimated_duration}",
            ""
        ]

        if plan.skipped_modules:
            lines.append("### ✅ 可跳过的模块")
            for m in plan.skipped_modules:
                lines.append(f"- ~~{m}~~")
            lines.append("")

        if plan.recommendations:
            lines.append("### 🧪 测试推荐")
            
            # 按优先级分组
            by_priority = {'critical': [], 'high': [], 'medium': [], 'low': []}
            for rec in plan.recommendations:
                by_priority[rec.priority].append(rec)

            for priority in ['critical', 'high', 'medium', 'low']:
                recs = by_priority[priority]
                if not recs:
                    continue
                
                emoji = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'}[priority]
                lines.append(f"\n#### {emoji} {priority.upper()}")
                
                for rec in recs:
                    lines.append(f"\n**{rec.test_type.upper()}** - {rec.description}")
                    lines.append(f"- 目标模块: `{', '.join(rec.target_modules[:3])}`")
                    lines.append(f"- 预估时间: {rec.estimated_duration}")
                    if rec.required:
                        lines.append(f"- ⚠️ 必须执行")
                    lines.append(f"- 类型: {self.TEST_TYPES[rec.test_type]['description']}")

        if plan.coverage_gaps:
            lines.append("\n### ⚠️ 测试覆盖缺口")
            for gap in plan.coverage_gaps:
                lines.append(f"- {gap}")

        return '\n'.join(lines)

    def _generate_job_for_recommendation(self, rec: TestRecommendation) -> str:
        """为单个推荐生成CI job"""
        job_name = f"{rec.test_type}-{rec.priority}"
        return f"""
  {job_name}:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run {rec.test_type} tests
        run: |
          echo "Running {rec.test_type} tests for: {', '.join(rec.target_modules[:2])}"
"""
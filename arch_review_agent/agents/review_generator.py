"""
Review Opinion Agent
负责综合前四个Agent的输出，生成结构化评审意见
"""

import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime

from .pr_analyzer import PRContext
from .rule_checker import RuleCheckResult
from .impact_evaluator import ImpactAssessmentResult


@dataclass
class ReviewComment:
    """单条评审意见"""
    category: str  # architecture, security, performance, testing, general
    severity: str  # critical, major, minor, suggestion
    title: str
    body: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    suggestions: List[str] = field(default_factory=list)


@dataclass
class ReviewSummary:
    """评审总结"""
    overall_score: float  # 0-100
    approval_status: str  # approved, conditional, rejected
    summary: str
    comments: List[ReviewComment] = field(default_factory=list)
    must_fix: List[str] = field(default_factory=list)  # 必须修复的问题
    should_fix: List[str] = field(default_factory=list)  # 建议修复的问题
    nit_picks: List[str] = field(default_factory=list)  # 小问题的提示


class ReviewOpinionAgent:
    """
    评审意见Agent：综合所有分析结果，生成结构化、可操作的评审意见
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.approval_threshold = self.config.get('approval_threshold', 70)
        self.conditional_threshold = self.config.get('conditional_threshold', 50)

    def generate(self, pr_context: PRContext, rule_result: RuleCheckResult, 
                 impact_result: ImpactAssessmentResult) -> ReviewSummary:
        """
        综合所有Agent的输出，生成评审意见
        """
        comments: List[ReviewComment] = []
        must_fix: List[str] = []
        should_fix: List[str] = []
        nit_picks: List[str] = []

        # 1. 分析规则检查结果
        self._process_rule_violations(rule_result, comments, must_fix, should_fix, nit_picks)

        # 2. 分析影响评估结果
        self._process_impact_result(impact_result, comments, must_fix, should_fix, nit_picks)

        # 3. 分析PR上下文
        self._process_pr_context(pr_context, comments, should_fix, nit_picks)

        # 4. 生成整体评分
        overall_score = self._calculate_overall_score(rule_result, impact_result, pr_context)

        # 5. 确定批准状态
        approval_status = self._determine_approval_status(
            overall_score, must_fix, rule_result, impact_result
        )

        # 6. 生成总结
        summary = self._generate_summary(
            pr_context, overall_score, approval_status, 
            len(comments), len(must_fix), len(should_fix)
        )

        return ReviewSummary(
            overall_score=overall_score,
            approval_status=approval_status,
            summary=summary,
            comments=sorted(comments, key=lambda x: (
                {'critical': 0, 'major': 1, 'minor': 2, 'suggestion': 3}[x.severity],
                {'architecture': 0, 'security': 1, 'performance': 2, 'testing': 3, 'general': 4}[x.category]
            )),
            must_fix=must_fix,
            should_fix=should_fix,
            nit_picks=nit_picks
        )

    def _process_rule_violations(self, rule_result: RuleCheckResult, 
                                 comments: List[ReviewComment],
                                 must_fix: List[str], should_fix: List[str], 
                                 nit_picks: List[str]):
        """处理规则违规结果"""
        # Critical issues
        for v in rule_result.critical_issues:
            comment = ReviewComment(
                category=self._categorize_rule(v.rule_id),
                severity='critical',
                title=f"严重: {v.rule_name}",
                body=f"{v.description}\n\n**文件:** `{v.file_path}`" + 
                     (f" **行号:** {v.line_number}" if v.line_number else ""),
                file_path=v.file_path,
                line_number=v.line_number,
                suggestions=[v.suggestion]
            )
            comments.append(comment)
            must_fix.append(f"修复 `{v.file_path}` 的 {v.rule_name}")

        # Warning issues
        for v in rule_result.warning_issues:
            comment = ReviewComment(
                category=self._categorize_rule(v.rule_id),
                severity='major' if v.severity == 'major' else 'minor',
                title=v.rule_name,
                body=v.description,
                file_path=v.file_path,
                line_number=v.line_number,
                suggestions=[v.suggestion]
            )
            comments.append(comment)
            should_fix.append(f"考虑修复 `{v.file_path}` 的 {v.rule_name}")

    def _process_impact_result(self, impact_result: ImpactAssessmentResult,
                               comments: List[ReviewComment],
                               must_fix: List[str], should_fix: List[str],
                               nit_picks: List[str]):
        """处理影响评估结果"""
        # Breaking changes
        for b in impact_result.breaking_changes:
            severity = 'critical' if b['severity'] == 'critical' else 'major'
            comment = ReviewComment(
                category='architecture',
                severity=severity,
                title=f"Breaking Change: {b['type']}",
                body=b['description'] + f"\n\n**文件:** `{b['file']}`",
                file_path=b['file'],
                suggestions=["确保下游服务同步更新", "准备兼容性方案"]
            )
            comments.append(comment)
            if severity == 'critical':
                must_fix.append(f"处理 {b['file']} 的Breaking Change")
            else:
                should_fix.append(f"关注 {b['file']} 的Breaking Change风险")

        # Cascade risk
        if impact_result.cascade_risk == 'high':
            comment = ReviewComment(
                category='architecture',
                severity='major',
                title="高级联风险",
                body=f"此PR可能影响 {len(impact_result.impacted_modules)} 个模块，建议分阶段部署验证。",
                suggestions=["建议先在staging环境部署验证", "准备回滚方案"]
            )
            comments.append(comment)
            should_fix.append("安排staging环境预验证")

        # Untested surface
        if impact_result.untested_surface:
            untested_count = len(impact_result.untested_surface)
            comment = ReviewComment(
                category='testing',
                severity='minor',
                title=f"未测试的受影响模块 ({untested_count})",
                body="以下模块受影响但可能缺少测试覆盖:\n" + 
                     "\n".join(f"- `{f}`" for f in impact_result.untested_surface[:5]),
                suggestions=["建议补充关键模块的测试"]
            )
            comments.append(comment)
            nit_picks.append(f"补充 {untested_count} 个模块的测试覆盖")

    def _process_pr_context(self, pr_context: PRContext,
                            comments: List[ReviewComment],
                            should_fix: List[str], nit_picks: List[str]):
        """处理PR上下文"""
        # Risk factors
        for risk in pr_context.risk_factors:
            comment = ReviewComment(
                category='general',
                severity='minor',
                title=f"风险提示: {risk}",
                body=risk,
                suggestions=[]
            )
            comments.append(comment)
            nit_picks.append(risk)

        # Low test coverage
        stats = pr_context.overall_stats
        if stats.get('total_files', 0) > 5:
            test_ratio = stats.get('test_file_count', 0) / stats.get('total_files', 1)
            if test_ratio < 0.15:
                comment = ReviewComment(
                    category='testing',
                    severity='suggestion',
                    title="测试覆盖率偏低",
                    body=f"测试文件比例仅 {test_ratio:.0%}，建议增加测试用例。",
                    suggestions=["为新增的核心逻辑编写测试"]
                )
                comments.append(comment)
                nit_picks.append(f"测试覆盖率偏低 ({test_ratio:.0%})")

    def _categorize_rule(self, rule_id: str) -> str:
        """将规则ID映射到分类"""
        if rule_id.startswith('SEC'):
            return 'security'
        elif rule_id.startswith('ARCH'):
            return 'architecture'
        elif rule_id.startswith('PERF'):
            return 'performance'
        elif rule_id.startswith('TEST'):
            return 'testing'
        else:
            return 'general'

    def _calculate_overall_score(self, rule_result: RuleCheckResult,
                                 impact_result: ImpactAssessmentResult,
                                 pr_context: PRContext) -> float:
        """计算整体评分"""
        # 合规评分 (权重50%)
        compliance_score = rule_result.compliance_score

        # 影响评分 (权重30%)
        # cascade_risk: high=0, medium=50, low=100
        cascade_scores = {'high': 0, 'medium': 50, 'low': 100}
        impact_score = cascade_scores.get(impact_result.cascade_risk, 50)

        # PR特性评分 (权重20%)
        # 根据风险因素和复杂度
        pr_score = 100
        if len(pr_context.risk_factors) > 3:
            pr_score -= (len(pr_context.risk_factors) - 3) * 10
        if impact_result.rollback_complexity == 'high':
            pr_score -= 15
        elif impact_result.rollback_complexity == 'medium':
            pr_score -= 5

        pr_score = max(0, min(100, pr_score))

        # 加权平均
        overall = compliance_score * 0.5 + impact_score * 0.3 + pr_score * 0.2

        return round(overall, 1)

    def _determine_approval_status(self, score: float, must_fix: List[str],
                                   rule_result: RuleCheckResult,
                                   impact_result: ImpactAssessmentResult) -> str:
        """确定批准状态"""
        # Critical issues 必须拒绝
        if len(rule_result.critical_issues) >= 2:
            return 'rejected'
        
        # 有Breaking Change需要conditional
        breaking_critical = [b for b in impact_result.breaking_changes if b['severity'] == 'critical']
        if breaking_critical:
            return 'conditional'

        # 高分不一定批准，考虑must_fix数量
        if len(must_fix) > 5:
            return 'conditional'
        
        if score >= self.approval_threshold and not must_fix:
            return 'approved'
        elif score >= self.conditional_threshold:
            return 'conditional'
        else:
            return 'rejected'

    def _generate_summary(self, pr_context: PRContext, score: float,
                          status: str, comment_count: int, 
                          must_count: int, should_count: int) -> str:
        """生成评审总结"""
        status_emoji = {'approved': '✅', 'conditional': '⚠️', 'rejected': '❌'}
        emoji = status_emoji.get(status, '❓')

        lines = [
            f"{emoji} **评审结果:** {status.replace('_', ' ').upper()}",
            f"**综合评分:** {score}/100",
            f"",
            f"PR #{pr_context.pr_number} \"{pr_context.title}\" ",
            f"涉及 {pr_context.overall_stats.get('total_files', 0)} 个文件，",
            f"{pr_context.overall_stats.get('total_additions', 0)} 行新增，{pr_context.overall_stats.get('total_deletions', 0)} 行删除。",
            f"",
        ]

        if status == 'approved':
            lines.append("🎉 所有检查通过，可以合并。")
        elif status == 'conditional':
            lines.append(f"请处理 {must_count} 个必须修复的问题后再合并。")
            if should_count > 0:
                lines.append(f"另有 {should_count} 个建议修复的问题。")
        else:
            lines.append(f"❌ 发现 {must_count} 个严重问题，需要重大修改后重新评审。")

        return '\n'.join(lines)

    def generate_markdown_report(self, summary: ReviewSummary) -> str:
        """生成Markdown格式的评审报告"""
        lines = [
            "# Code Review Report",
            "",
            summary.summary,
            "",
            "---",
            "",
        ]

        if summary.must_fix:
            lines.extend([
                "## 🚨 必须修复 (Must Fix)",
                ""
            ])
            for item in summary.must_fix:
                lines.append(f"- {item}")
            lines.append("")

        if summary.should_fix:
            lines.extend([
                "## ⚠️ 建议修复 (Should Fix)",
                ""
            ])
            for item in summary.should_fix:
                lines.append(f"- {item}")
            lines.append("")

        if summary.nit_picks:
            lines.extend([
                "## 💡 小问题 (Nit Picks)",
                ""
            ])
            for item in summary.nit_picks:
                lines.append(f"- {item}")
            lines.append("")

        if summary.comments:
            lines.extend([
                "## 📝 详细评审意见",
                ""
            ])
            
            # 按分类分组
            by_category = {}
            for c in summary.comments:
                if c.category not in by_category:
                    by_category[c.category] = []
                by_category[c.category].append(c)

            for category, category_comments in by_category.items():
                lines.append(f"### {category.upper()}")
                for comment in category_comments:
                    severity_icon = {
                        'critical': '🔴',
                        'major': '🟠',
                        'minor': '🟡',
                        'suggestion': '💬'
                    }.get(comment.severity, '•')
                    lines.append(f"\n#### {severity_icon} {comment.title}")
                    lines.append(f"\n{comment.body}")
                    if comment.file_path:
                        location = f"`{comment.file_path}`"
                        if comment.line_number:
                            location += f" @ line {comment.line_number}"
                        lines.append(f"\n**位置:** {location}")
                    if comment.suggestions:
                        lines.append("\n**建议:**")
                        for s in comment.suggestions:
                            lines.append(f"- {s}")

        return '\n'.join(lines)
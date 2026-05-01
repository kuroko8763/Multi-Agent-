"""
PR Understanding Agent
负责解析代码变更 + 关联 Issue/需求文档，理解PR的上下文和意图
"""

import re
import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path


@dataclass
class FileChange:
    """单个文件的变更信息"""
    file_path: str
    change_type: str  # added, modified, deleted, renamed
    additions: int
    deletions: int
    diff_content: str
    language: str
    is_test: bool
    is_config: bool
    is_documentation: bool


@dataclass
class CommitInfo:
    """提交信息"""
    hash: str
    author: str
    date: datetime
    message: str
    files: List[str]


@dataclass
class LinkedIssue:
    """关联的Issue"""
    issue_id: str
    title: str
    status: str
    priority: str
    labels: List[str]


@dataclass
class PRContext:
    """PR理解的完整上下文"""
    pr_number: int
    title: str
    description: str
    author: str
    base_branch: str
    head_branch: str
    created_at: datetime
    changed_files: List[FileChange] = field(default_factory=list)
    commits: List[CommitInfo] = field(default_factory=list)
    linked_issues: List[LinkedIssue] = field(default_factory=list)
    overall_stats: Dict[str, Any] = field(default_factory=dict)
    intent_summary: str = ""
    technical_domain: str = ""  # frontend/backend/database/infrastructure
    risk_factors: List[str] = field(default_factory=list)


class PRUnderstandingAgent:
    """
    PR理解Agent：解析PR的变更内容、关联上下文、识别意图和风险
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.supported_languages = {
            '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
            '.java': 'java', '.go': 'go', '.rs': 'rust', '.cpp': 'cpp',
            '.c': 'c', '.rb': 'ruby', '.php': 'php', '.cs': 'csharp',
            '.vue': 'vue', '.jsx': 'jsx', '.tsx': 'tsx'
        }
        self.config_patterns = {
            'docker': ['Dockerfile', 'docker-compose', '.dockerignore'],
            'ci': ['Jenkinsfile', '.gitlab-ci.yml', 'azure-pipelines.yml', 'github-actions'],
            'k8s': ['k8s', 'kubernetes', 'helm'],
            'infra': ['terraform', 'ansible', 'cloudformation'],
            'config': ['config', 'settings', '.env', '.yaml', '.yml', '.json', '.toml']
        }

    def analyze(self, pr_data: Dict[str, Any]) -> PRContext:
        """
        分析PR并返回完整上下文
        pr_data格式:
        {
            'pr_number': int,
            'title': str,
            'description': str,
            'author': str,
            'base_branch': str,
            'head_branch': str,
            'created_at': str,
            'files': [{'path': str, 'diff': str, 'status': str}, ...],
            'commits': [{'hash': str, 'author': str, 'message': str, 'date': str}, ...],
            'linked_issues': [{'id': str, 'title': str, 'status': str}, ...]
        }
        """
        context = PRContext(
            pr_number=pr_data.get('pr_number', 0),
            title=pr_data.get('title', ''),
            description=pr_data.get('description', ''),
            author=pr_data.get('author', 'unknown'),
            base_branch=pr_data.get('base_branch', 'main'),
            head_branch=pr_data.get('head_branch', ''),
            created_at=self._parse_datetime(pr_data.get('created_at', ''))
        )

        # 分析文件变更
        context.changed_files = self._analyze_files(pr_data.get('files', []))

        # 分析提交历史
        context.commits = self._analyze_commits(pr_data.get('commits', []))

        # 关联Issues
        context.linked_issues = self._parse_linked_issues(pr_data.get('linked_issues', []))

        # 整体统计
        context.overall_stats = self._compute_stats(context)

        # 意图推断
        context.intent_summary = self._infer_intent(context)

        # 技术领域识别
        context.technical_domain = self._identify_domain(context)

        # 风险因素识别
        context.risk_factors = self._identify_risk_factors(context)

        return context

    def _analyze_files(self, files_data: List[Dict]) -> List[FileChange]:
        """分析文件变更列表"""
        changes = []
        for f in files_data:
            file_path = f.get('path', '')
            diff = f.get('diff', '')
            
            change = FileChange(
                file_path=file_path,
                change_type=self._get_change_type(f.get('status', 'modified')),
                additions=self._count_additions(diff),
                deletions=self._count_deletions(diff),
                diff_content=diff,
                language=self._detect_language(file_path),
                is_test=self._is_test_file(file_path),
                is_config=self._is_config_file(file_path),
                is_documentation=self._is_documentation(file_path)
            )
            changes.append(change)
        
        return changes

    def _analyze_commits(self, commits_data: List[Dict]) -> List[CommitInfo]:
        """分析提交历史"""
        commits = []
        for c in commits_data:
            commit = CommitInfo(
                hash=c.get('hash', '')[:12],
                author=c.get('author', ''),
                date=self._parse_datetime(c.get('date', '')),
                message=c.get('message', ''),
                files=c.get('files', [])
            )
            commits.append(commit)
        return commits

    def _parse_linked_issues(self, issues_data: List[Dict]) -> List[LinkedIssue]:
        """解析关联的Issue"""
        issues = []
        for i in issues_data:
            issue = LinkedIssue(
                issue_id=i.get('id', ''),
                title=i.get('title', ''),
                status=i.get('status', 'unknown'),
                priority=i.get('priority', 'medium'),
                labels=i.get('labels', [])
            )
            issues.append(issue)
        return issues

    def _compute_stats(self, context: PRContext) -> Dict[str, Any]:
        """计算整体统计信息"""
        files = context.changed_files
        total_adds = sum(f.additions for f in files)
        total_dels = sum(f.deletions for f in files)
        
        # 语言分布
        lang_counts = {}
        for f in files:
            lang = f.language
            lang_counts[lang] = lang_counts.get(lang, 0) + 1

        # 文件类型分布
        test_count = sum(1 for f in files if f.is_test)
        config_count = sum(1 for f in files if f.is_config)
        doc_count = sum(1 for f in files if f.is_documentation)

        # 按目录分组（简化处理）
        dir_groups = {}
        for f in files:
            parts = f.file_path.split('/')
            dir_name = parts[0] if parts else 'root'
            dir_groups[dir_name] = dir_groups.get(dir_name, 0) + 1

        return {
            'total_files': len(files),
            'total_additions': total_adds,
            'total_deletions': total_dels,
            'total_lines_changed': total_adds + total_dels,
            'language_distribution': lang_counts,
            'test_file_count': test_count,
            'config_file_count': config_count,
            'doc_file_count': doc_count,
            'directory_distribution': dir_groups,
            'commit_count': len(context.commits),
            'issue_count': len(context.linked_issues)
        }

    def _infer_intent(self, context: PRContext) -> str:
        """推断PR的意图"""
        title = context.title.lower()
        description = context.description.lower()
        combined = title + ' ' + description

        intent_patterns = {
            'feature': ['add', 'implement', 'new', 'feature', '功能', '新增'],
            'bugfix': ['fix', 'bug', '修复', 'hotfix', 'patch'],
            'refactor': ['refactor', '重构', '优化', 'improve', 'cleanup'],
            'docs': ['docs', 'document', '文档', 'readme', 'changelog'],
            'test': ['test', 'spec', '测试', 'coverage'],
            'chore': ['chore', 'deps', 'dependency', 'bump', '依赖'],
            'security': ['security', 'vulnerability', '安全', 'auth'],
            'performance': ['performance', 'optimize', '性能', 'cache'],
            'migration': ['migrate', 'migration', '迁移', 'upgrade']
        }

        matched_intents = []
        for intent, keywords in intent_patterns.items():
            if any(kw in combined for kw in keywords):
                matched_intents.append(intent)

        if not matched_intents:
            matched_intents = ['unknown']

        # 根据文件类型进一步确认
        if not any(i in matched_intents for i in ['feature', 'bugfix']):
            if context.overall_stats.get('config_file_count', 0) > 3:
                matched_intents.append('infrastructure')
            if context.overall_stats.get('test_file_count', 0) > context.overall_stats.get('total_files', 1) / 2:
                matched_intents.append('test_coverage')

        return ', '.join(set(matched_intents))

    def _identify_domain(self, context: PRContext) -> str:
        """识别技术领域"""
        lang_dist = context.overall_stats.get('language_distribution', {})
        
        if not lang_dist:
            return 'unknown'
        
        dominant_lang = max(lang_dist, key=lang_dist.get)
        
        domain_mapping = {
            'python': 'backend',
            'java': 'backend',
            'go': 'backend',
            'rust': 'backend',
            'javascript': 'frontend',
            'typescript': 'frontend',
            'vue': 'frontend',
            'jsx': 'frontend',
            'tsx': 'frontend'
        }
        
        domain = domain_mapping.get(dominant_lang, 'fullstack')
        
        # 根据路径进一步判断
        for f in context.changed_files:
            if 'k8s/' in f.file_path or 'kubernetes/' in f.file_path:
                return 'infrastructure'
            if 'db/' in f.file_path or 'migrations/' in f.file_path:
                return 'database'
        
        return domain

    def _identify_risk_factors(self, context: PRContext) -> List[str]:
        """识别风险因素"""
        risks = []
        stats = context.overall_stats
        
        # 文件数量过多
        if stats.get('total_files', 0) > 20:
            risks.append(f"Large change: {stats['total_files']} files")
        
        # 大量删除
        if stats.get('total_deletions', 0) > 500:
            risks.append(f"Heavy deletion: {stats['total_deletions']} lines")
        
        # 深夜/周末提交
        if context.created_at.weekday() >= 5:  # weekend
            risks.append("Weekend commit")
        if context.created_at.hour < 7 or context.created_at.hour > 22:
            risks.append("Off-hours commit")
        
        # 无关联Issue
        if not context.linked_issues and stats.get('total_files', 0) > 5:
            risks.append("No linked issue for large change")
        
        # 配置类文件变更
        if stats.get('config_file_count', 0) > 5:
            risks.append(f"Many config files: {stats['config_file_count']}")
        
        # 缺少测试
        total_files = stats.get('total_files', 1)
        test_ratio = stats.get('test_file_count', 0) / total_files
        if test_ratio < 0.1 and total_files > 5:
            risks.append(f"Low test coverage: {test_ratio:.0%}")
        
        # 多语言混杂
        if len(stats.get('language_distribution', {})) > 3:
            risks.append(f"Multi-language change: {len(stats['language_distribution'])} languages")
        
        # 数据库变更
        for f in context.changed_files:
            if any(x in f.file_path.lower() for x in ['migration', 'schema', 'db']):
                risks.append("Database schema change detected")
                break
        
        return risks

    def _get_change_type(self, status: str) -> str:
        """解析变更类型"""
        status_lower = status.lower()
        if 'add' in status_lower or 'new' in status_lower:
            return 'added'
        elif 'delete' in status_lower:
            return 'deleted'
        elif 'rename' in status_lower:
            return 'renamed'
        else:
            return 'modified'

    def _count_additions(self, diff: str) -> int:
        """统计增加行数"""
        return sum(1 for line in diff.split('\n') if line.startswith('+') and not line.startswith('+++'))

    def _count_deletions(self, diff: str) -> int:
        """统计删除行数"""
        return sum(1 for line in diff.split('\n') if line.startswith('-') and not line.startswith('---'))

    def _detect_language(self, file_path: str) -> str:
        """检测编程语言"""
        ext = Path(file_path).suffix
        return self.supported_languages.get(ext, 'unknown')

    def _is_test_file(self, file_path: str) -> bool:
        """判断是否为测试文件"""
        patterns = ['test', 'spec', '_test', 'tests', '__tests__', '.test.', '.spec.']
        return any(p in file_path for p in patterns)

    def _is_config_file(self, file_path: str) -> bool:
        """判断是否为配置文件"""
        for category, patterns in self.config_patterns.items():
            if any(p in file_path.lower() for p in patterns):
                return True
        return False

    def _is_documentation(self, file_path: str) -> bool:
        """判断是否为文档"""
        doc_patterns = ['readme', 'changelog', 'docs/', '.md', 'doc/', 'api/']
        return any(p in file_path.lower() for p in doc_patterns)

    def _parse_datetime(self, date_str: str) -> datetime:
        """解析时间字符串"""
        if not date_str:
            return datetime.now()
        try:
            # 尝试ISO格式
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except Exception:
            try:
                # 尝试其他格式
                return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            except Exception:
                return datetime.now()

    def generate_summary(self, context: PRContext) -> str:
        """生成PR摘要文本"""
        stats = context.overall_stats
        lines = [
            f"## PR #{context.pr_number}: {context.title}",
            f"**Author:** {context.author} | **Domain:** {context.technical_domain}",
            f"**Intent:** {context.intent_summary}",
            "",
            f"### 变更统计",
            f"- 文件数: {stats.get('total_files', 0)}",
            f"- 新增: +{stats.get('total_additions', 0)} / 删除: -{stats.get('total_deletions', 0)}",
            f"- 语言: {', '.join(stats.get('language_distribution', {}).keys())}",
            "",
        ]
        
        if context.risk_factors:
            lines.append("### 风险因素")
            for risk in context.risk_factors:
                lines.append(f"- ⚠️ {risk}")
            lines.append("")
        
        if context.linked_issues:
            lines.append("### 关联Issue")
            for issue in context.linked_issues:
                lines.append(f"- #{issue.issue_id}: {issue.title}")
            lines.append("")
        
        return '\n'.join(lines)
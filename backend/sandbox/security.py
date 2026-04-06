"""沙箱安全策略模块

提供静态代码分析、执行控制、异常隔离功能。
使用 AST 解析检查危险操作。
"""

import ast
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RiskLevel(Enum):
    """风险等级"""

    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityCheckResult:
    """安全检查结果"""

    is_safe: bool
    risk_level: RiskLevel
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocked_imports: list[str] = field(default_factory=list)
    blocked_functions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "is_safe": self.is_safe,
            "risk_level": self.risk_level.value,
            "issues": self.issues,
            "warnings": self.warnings,
            "blocked_imports": self.blocked_imports,
            "blocked_functions": self.blocked_functions,
        }


@dataclass
class ExecutionLimits:
    """执行限制配置"""

    timeout: int = 60
    memory_limit: str = "512m"
    cpu_limit: float = 0.5
    max_output_size: int = 1024 * 1024
    max_file_size: int = 10 * 1024 * 1024


BLOCKED_IMPORTS = {
    "os": "禁止使用 os 模块",
    "subprocess": "禁止使用 subprocess 模块",
    "socket": "禁止使用 socket 模块",
    "socketserver": "禁止使用 socketserver 模块",
    "http.server": "禁止使用 http.server 模块",
    "http.client": "禁止使用 http.client 模块",
    "urllib": "禁止使用 urllib 模块",
    "urllib2": "禁止使用 urllib2 模块",
    "urllib3": "禁止使用 urllib3 模块",
    "requests": "禁止使用 requests 模块",
    "ftplib": "禁止使用 ftplib 模块",
    "telnetlib": "禁止使用 telnetlib 模块",
    "smtplib": "禁止使用 smtplib 模块",
    "poplib": "禁止使用 poplib 模块",
    "imaplib": "禁止使用 imaplib 模块",
    "nntplib": "禁止使用 nntplib 模块",
    "pickle": "禁止使用 pickle 模块（安全风险）",
    "shelve": "禁止使用 shelve 模块",
    "marshal": "禁止使用 marshal 模块",
    "ctypes": "禁止使用 ctypes 模块",
    "multiprocessing": "禁止使用 multiprocessing 模块",
    "threading": "禁止使用 threading 模块",
    "_thread": "禁止使用 _thread 模块",
    "signal": "禁止使用 signal 模块",
    "resource": "禁止使用 resource 模块",
    "syslog": "禁止使用 syslog 模块",
    "logging.handlers": "禁止使用 logging.handlers 模块",
    "builtins": "禁止直接访问 builtins 模块",
    "__import__": "禁止使用 __import__ 函数",
    "importlib": "禁止使用 importlib 模块",
    "code": "禁止使用 code 模块",
    "codeop": "禁止使用 codeop 模块",
    "compile": "禁止使用 compile 函数",
    "exec": "禁止使用 exec 函数",
    "eval": "禁止使用 eval 函数",
    "globals": "禁止使用 globals 函数",
    "locals": "禁止使用 locals 函数",
    "vars": "禁止使用 vars 函数",
    "dir": "禁止使用 dir 函数",
    "getattr": "禁止使用 getattr 函数",
    "setattr": "禁止使用 setattr 函数",
    "delattr": "禁止使用 delattr 函数",
    "hasattr": "禁止使用 hasattr 函数",
    "open": "禁止使用 open 函数（请使用沙箱提供的文件接口）",
    "input": "禁止使用 input 函数",
    "breakpoint": "禁止使用 breakpoint 函数",
}

BLOCKED_FUNCTIONS = {
    "exec": "禁止使用 exec 函数",
    "eval": "禁止使用 eval 函数",
    "compile": "禁止使用 compile 函数",
    "__import__": "禁止使用 __import__ 函数",
    "open": "禁止使用 open 函数",
    "input": "禁止使用 input 函数",
    "breakpoint": "禁止使用 breakpoint 函数",
}

BLOCKED_PATTERNS = [
    (r"__\w+__", "禁止使用双下划线属性/方法"),
    (r"getattr\s*\(", "禁止使用 getattr 函数"),
    (r"setattr\s*\(", "禁止使用 setattr 函数"),
    (r"delattr\s*\(", "禁止使用 delattr 函数"),
    (r"hasattr\s*\(", "禁止使用 hasattr 函数"),
    (r"globals\s*\(", "禁止使用 globals 函数"),
    (r"locals\s*\(", "禁止使用 locals 函数"),
    (r"vars\s*\(", "禁止使用 vars 函数"),
    (r"dir\s*\(", "禁止使用 dir 函数"),
    (r"type\s*\(", "禁止使用 type 函数"),
    (r"super\s*\(", "禁止使用 super 函数"),
    (r"object\s*\.", "禁止直接访问 object 属性"),
    (r"classmethod\s*\(", "禁止使用 classmethod 装饰器"),
    (r"staticmethod\s*\(", "禁止使用 staticmethod 装饰器"),
    (r"property\s*\(", "禁止使用 property 装饰器"),
]


class StaticCodeAnalyzer:
    """静态代码分析器

    使用 AST 解析检查代码中的危险操作。
    """

    def __init__(self) -> None:
        """初始化分析器"""
        self._issues: list[str] = []
        self._warnings: list[str] = []
        self._blocked_imports: list[str] = []
        self._blocked_functions: list[str] = []

    def analyze(self, code: str) -> SecurityCheckResult:
        """分析代码安全性

        Args:
            code: 要分析的 Python 代码

        Returns:
            安全检查结果
        """
        self._issues = []
        self._warnings = []
        self._blocked_imports = []
        self._blocked_functions = []

        self._check_patterns(code)

        try:
            tree = ast.parse(code)
            self._analyze_ast(tree)
        except SyntaxError as e:
            self._issues.append(f"语法错误: {e}")
            return SecurityCheckResult(
                is_safe=False,
                risk_level=RiskLevel.CRITICAL,
                issues=self._issues,
                warnings=self._warnings,
                blocked_imports=self._blocked_imports,
                blocked_functions=self._blocked_functions,
            )

        risk_level = self._determine_risk_level()

        return SecurityCheckResult(
            is_safe=risk_level in (RiskLevel.SAFE, RiskLevel.LOW),
            risk_level=risk_level,
            issues=self._issues,
            warnings=self._warnings,
            blocked_imports=self._blocked_imports,
            blocked_functions=self._blocked_functions,
        )

    def _check_patterns(self, code: str) -> None:
        """检查危险模式"""
        for pattern, message in BLOCKED_PATTERNS:
            if re.search(pattern, code):
                self._warnings.append(message)

    def _analyze_ast(self, tree: ast.AST) -> None:
        """分析 AST 树"""
        for node in ast.walk(tree):
            self._check_node(node)

    def _check_node(self, node: ast.AST) -> None:
        """检查单个 AST 节点"""
        if isinstance(node, ast.Import):
            self._check_import(node)
        elif isinstance(node, ast.ImportFrom):
            self._check_import_from(node)
        elif isinstance(node, ast.Call):
            self._check_call(node)
        elif isinstance(node, ast.Attribute):
            self._check_attribute(node)
        elif isinstance(node, ast.Name):
            self._check_name(node)

    def _check_import(self, node: ast.Import) -> None:
        """检查 import 语句"""
        for alias in node.names:
            module_name = alias.name.split(".")[0]
            if module_name in BLOCKED_IMPORTS:
                self._blocked_imports.append(module_name)
                self._issues.append(BLOCKED_IMPORTS[module_name])

    def _check_import_from(self, node: ast.ImportFrom) -> None:
        """检查 from ... import 语句"""
        if node.module is None:
            return

        module_name = node.module.split(".")[0]
        if module_name in BLOCKED_IMPORTS:
            self._blocked_imports.append(module_name)
            self._issues.append(BLOCKED_IMPORTS[module_name])

        for alias in node.names:
            full_name = f"{node.module}.{alias.name}"
            if full_name in BLOCKED_IMPORTS:
                self._blocked_imports.append(full_name)
                self._issues.append(BLOCKED_IMPORTS[full_name])

    def _check_call(self, node: ast.Call) -> None:
        """检查函数调用"""
        func_name = self._get_func_name(node)
        if func_name and func_name in BLOCKED_FUNCTIONS:
            self._blocked_functions.append(func_name)
            self._issues.append(BLOCKED_FUNCTIONS[func_name])

    def _check_attribute(self, node: ast.Attribute) -> None:
        """检查属性访问"""
        if node.attr.startswith("_"):
            self._warnings.append(f"访问私有属性: {node.attr}")

    def _check_name(self, node: ast.Name) -> None:
        """检查变量名"""
        if (
            node.id.startswith("__")
            and node.id.endswith("__")
            and node.id not in ["__name__", "__file__", "__doc__"]
        ):
            self._warnings.append(f"访问特殊属性: {node.id}")

    def _get_func_name(self, node: ast.Call) -> str | None:
        """获取函数名"""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return node.func.attr
        return None

    def _determine_risk_level(self) -> RiskLevel:
        """确定风险等级"""
        if self._blocked_imports or self._blocked_functions:
            return RiskLevel.CRITICAL

        if len(self._issues) > 0:
            return RiskLevel.HIGH

        if len(self._warnings) > 3:
            return RiskLevel.MEDIUM

        if len(self._warnings) > 0:
            return RiskLevel.LOW

        return RiskLevel.SAFE


class SecurityPolicy:
    """安全策略

    提供代码安全检查和执行控制。
    """

    def __init__(
        self,
        limits: ExecutionLimits | None = None,
        strict_mode: bool = True,
    ) -> None:
        """初始化安全策略

        Args:
            limits: 执行限制配置
            strict_mode: 是否启用严格模式
        """
        self._limits = limits or ExecutionLimits()
        self._strict_mode = strict_mode
        self._analyzer = StaticCodeAnalyzer()

    def check_code(self, code: str) -> SecurityCheckResult:
        """检查代码安全性

        Args:
            code: 要检查的代码

        Returns:
            安全检查结果
        """
        return self._analyzer.analyze(code)

    def is_execution_allowed(self, code: str) -> tuple[bool, str]:
        """检查是否允许执行

        Args:
            code: 要检查的代码

        Returns:
            (是否允许执行, 原因)
        """
        result = self.check_code(code)

        if not result.is_safe:
            if self._strict_mode:
                return False, f"代码安全检查未通过: {', '.join(result.issues)}"
            else:
                if result.risk_level == RiskLevel.CRITICAL:
                    return False, f"代码包含高危操作: {', '.join(result.issues)}"

        return True, "代码安全检查通过"

    def get_limits(self) -> ExecutionLimits:
        """获取执行限制"""
        return self._limits

    def sanitize_output(self, output: str) -> str:
        """清理输出

        Args:
            output: 原始输出

        Returns:
            清理后的输出
        """
        if len(output) > self._limits.max_output_size:
            return output[: self._limits.max_output_size] + "\n... [输出已截断]"

        return output

    def create_safe_error_message(self, error: str) -> str:
        """创建安全的错误信息

        Args:
            error: 原始错误信息

        Returns:
            安全的错误信息
        """
        sanitized = error

        sanitized = re.sub(r"/home/\w+/", "/home/[user]/", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"/Users/\w+/", "/Users/[user]/", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"C:\\Users\\[^\s\\]+\\", r"C:\\Users\\[user]\\", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"api[_-]?key[=:]\s*\S+", "api_key=[REDACTED]", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"password[=:]\s*\S+", "password=[REDACTED]", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"token[=:]\s*\S+", "token=[REDACTED]", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"secret[=:]\s*\S+", "secret=[REDACTED]", sanitized, flags=re.IGNORECASE)

        return sanitized


def analyze_code(code: str) -> SecurityCheckResult:
    """分析代码安全性（便捷函数）

    Args:
        code: 要分析的代码

    Returns:
        安全检查结果
    """
    analyzer = StaticCodeAnalyzer()
    return analyzer.analyze(code)


def is_code_safe(code: str) -> bool:
    """检查代码是否安全（便捷函数）

    Args:
        code: 要检查的代码

    Returns:
        代码是否安全
    """
    result = analyze_code(code)
    return result.is_safe

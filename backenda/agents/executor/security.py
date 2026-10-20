"""
Static code analysis, AST inspection, and security policy enforcement for untrusted training packages.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Optional, Set

from app.core.logging import get_logger

logger = get_logger("adc.executor.security")


class SecurityViolationError(Exception):
    """Raised when an untrusted code package breaches security boundaries."""
    pass


# High-risk standard library or foreign modules banned from direct import
BANNED_MODULES: Set[str] = {
    "ctypes",
    "pty",
    "code",
    "codeop",
    "commands",
    "posix",
    "nt",
}

# Dangerous os / system call names banned in training packages
BANNED_OS_CALLS: Set[str] = {
    "system",
    "popen",
    "popen2",
    "popen3",
    "popen4",
    "spawnl",
    "spawnle",
    "spawnlp",
    "spawnlpe",
    "spawnv",
    "spawnve",
    "spawnvp",
    "spawnvpe",
    "execl",
    "execle",
    "execlp",
    "execlpe",
    "execv",
    "execve",
    "execvp",
    "execvpe",
}

# Critical system sensitive strings and path tokens banned in code literals
SENSITIVE_STRING_PATTERNS: Set[str] = {
    "/etc/shadow",
    "/etc/passwd",
    "C:\\Windows\\System32",
    ".aws/credentials",
    "id_rsa",
    "id_ed25519",
    "/var/run/docker.sock",
    "\\\\.\\pipe\\docker_engine",
}


class CodeASTVisitor(ast.NodeVisitor):
    """AST visitor inspecting AST nodes for dangerous imports, function calls, and literals."""

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.violations: List[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            base_module = alias.name.split(".")[0]
            if base_module in BANNED_MODULES:
                self.violations.append(
                    f"Line {node.lineno}: Banned module '{alias.name}' import detected in {self.filename}."
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            base_module = node.module.split(".")[0]
            if base_module in BANNED_MODULES:
                self.violations.append(
                    f"Line {node.lineno}: Banned module '{node.module}' import detected in {self.filename}."
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # Detect calls like os.system(...) or subprocess.Popen(...)
        if isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if attr_name in BANNED_OS_CALLS:
                self.violations.append(
                    f"Line {node.lineno}: Dangerous OS execution call '{attr_name}()' detected in {self.filename}."
                )

        # Detect built-in eval / exec on dynamic payloads
        if isinstance(node.func, ast.Name):
            if node.func.id in {"eval", "exec"} and node.args:
                # If argument is not a literal string, flag as high risk dynamic evaluation
                if not isinstance(node.args[0], ast.Constant):
                    self.violations.append(
                        f"Line {node.lineno}: Dynamic '{node.func.id}()' code evaluation detected in {self.filename}."
                    )

        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str):
            val = node.value.strip()
            for pattern in SENSITIVE_STRING_PATTERNS:
                if pattern.lower() in val.lower():
                    self.violations.append(
                        f"Line {node.lineno}: Access attempt to sensitive host resource '{pattern}' in {self.filename}."
                    )
        self.generic_visit(node)


class CodeSecurityScanner:
    """
    Static analyzer validating untrusted Python training packages before execution.
    """

    @classmethod
    def scan_code_string(cls, code: str, filename: str = "script.py") -> List[str]:
        """Parse and scan a Python source code string."""
        try:
            tree = ast.parse(code, filename=filename)
        except SyntaxError as exc:
            return [f"Syntax error parsing {filename} at line {exc.lineno}: {exc.msg}"]

        visitor = CodeASTVisitor(filename=filename)
        visitor.visit(tree)
        return visitor.violations

    @classmethod
    def scan_file(cls, file_path: Path | str) -> List[str]:
        """Scan a single Python file."""
        path = Path(file_path)
        if not path.is_file():
            return [f"File does not exist: {path}"]

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            return [f"Could not read {path.name}: {exc}"]

        return cls.scan_code_string(content, filename=path.name)

    @classmethod
    def scan_package_directory(cls, package_dir: Path | str) -> None:
        """
        Scan all Python scripts in an extracted package directory.
        Raises SecurityViolationError if any policy violation is detected.
        """
        root = Path(package_dir)
        all_violations: List[str] = []

        for py_file in root.rglob("*.py"):
            violations = cls.scan_file(py_file)
            if violations:
                all_violations.extend(violations)

        if all_violations:
            logger.error("security_scan_violations_detected", violations=all_violations)
            raise SecurityViolationError(
                f"Package failed security policy verification with {len(all_violations)} violation(s): "
                + "; ".join(all_violations)
            )

        logger.info("security_scan_passed", scanned_dir=str(root))

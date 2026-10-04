"""Remove build-user prefixes only from CPython's generated build configuration."""

import ast
import re
from types import CodeType

_PERSONAL_PREFIX = re.compile(r"/(?:Users|home)/[A-Za-z0-9_.-]+(?=/|$)")


def sanitize_build_string(value: str) -> str:
    """Keep compiler arguments and path suffixes, without a builder's account name."""
    return _PERSONAL_PREFIX.sub("/usr/src/python-build", value)


def sanitize_sysconfig_source(source: str) -> str:
    """Preserve the generated mapping's keys, non-path values, and value types."""
    tree = ast.parse(source)
    assignments = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "build_time_vars" for target in node.targets)
    ]
    if len(assignments) != 1 or not isinstance(assignments[0].value, ast.Dict):
        raise ValueError("Unexpected CPython build_time_vars source structure")
    for node in ast.walk(assignments[0].value):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            node.value = sanitize_build_string(node.value)
    return ast.unparse(tree) + "\n"


def sanitize_sysconfig_bytecode(code: CodeType) -> CodeType:
    """Cover Nuitka's frozen stdlib path while preserving bytecode and ABI values."""
    constants = tuple(
        sanitize_sysconfig_bytecode(value)
        if isinstance(value, CodeType)
        else sanitize_build_string(value)
        if isinstance(value, str)
        else value
        for value in code.co_consts
    )
    return code.replace(co_consts=constants)

import ast

import pytest

from scripts.python_build_privacy import sanitize_sysconfig_bytecode, sanitize_sysconfig_source


@pytest.mark.parametrize("builder_root", ["/home/SYNTHETIC-BUILDER", "/Users/SYNTHETIC-BUILDER"])
def test_sysconfig_mapping_preserves_abi_and_compiler_options(builder_root: str) -> None:
    values = {
        "SOABI": "cpython-313-x86_64-linux-gnu",
        "MULTIARCH": "x86_64-linux-gnu",
        "MACOSX_DEPLOYMENT_TARGET": "13.0",
        "Py_ENABLE_SHARED": 1,
        "CONFIG_ARGS": f"'--enable-shared' '--with-openssl={builder_root}/openssl'",
        "CFLAGS": f"-O3 -I{builder_root}/include -fno-strict-aliasing",
        "srcdir": f"{builder_root}/Python-3.13.15",
        "prefix": "/usr/local",
        "missing": None,
    }
    source = f"build_time_vars = {values!r}\n"
    expected = {
        **values,
        "CONFIG_ARGS": "'--enable-shared' '--with-openssl=/usr/src/python-build/openssl'",
        "CFLAGS": "-O3 -I/usr/src/python-build/include -fno-strict-aliasing",
        "srcdir": "/usr/src/python-build/Python-3.13.15",
    }
    transformed = sanitize_sysconfig_source(source)
    assert ast.literal_eval(ast.parse(transformed).body[0].value) == expected
    original_code = compile(source, "_sysconfigdata.py", "exec")
    frozen_code = sanitize_sysconfig_bytecode(original_code)
    namespace: dict[str, object] = {}
    exec(frozen_code, namespace)
    assert namespace["build_time_vars"] == expected
    assert frozen_code.co_code == original_code.co_code
    assert frozen_code.co_filename == original_code.co_filename


@pytest.mark.parametrize("source", ["unexpected = {}", "build_time_vars = load_configuration()"])
def test_unexpected_sysconfig_structure_fails_closed(source: str) -> None:
    with pytest.raises(ValueError, match="Unexpected CPython"):
        sanitize_sysconfig_source(source)

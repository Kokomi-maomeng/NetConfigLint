"""Build-only Nuitka hook for CPython's generated sysconfigdata module."""

import sysconfig

from nuitka.plugins.PluginBase import NuitkaPluginBase

from scripts.python_build_privacy import sanitize_sysconfig_bytecode, sanitize_sysconfig_source


class NetConfigLintBuildPrivacy(NuitkaPluginBase):
    plugin_name = "netconfiglint-build-privacy"

    def onModuleSourceCode(self, module_name, source_filename, source_code):
        if str(module_name) == sysconfig._get_sysconfigdata_name():
            return sanitize_sysconfig_source(source_code)
        return source_code

    def onFrozenModuleBytecode(self, module_name, is_package, bytecode):
        if str(module_name) == sysconfig._get_sysconfigdata_name():
            return sanitize_sysconfig_bytecode(bytecode)
        return bytecode

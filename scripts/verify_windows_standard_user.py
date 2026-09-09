"""Run a portable smoke without elevation; use a restricted LUA token if UAC is disabled."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
from ctypes import wintypes as w
from pathlib import Path


class StartupInfo(ctypes.Structure):
    _fields_ = [
        ("cb", w.DWORD),
        ("lpReserved", w.LPWSTR),
        ("lpDesktop", w.LPWSTR),
        ("lpTitle", w.LPWSTR),
        ("dwX", w.DWORD),
        ("dwY", w.DWORD),
        ("dwXSize", w.DWORD),
        ("dwYSize", w.DWORD),
        ("dwXCountChars", w.DWORD),
        ("dwYCountChars", w.DWORD),
        ("dwFillAttribute", w.DWORD),
        ("dwFlags", w.DWORD),
        ("wShowWindow", w.WORD),
        ("cbReserved2", w.WORD),
        ("lpReserved2", ctypes.POINTER(w.BYTE)),
        ("hStdInput", w.HANDLE),
        ("hStdOutput", w.HANDLE),
        ("hStdError", w.HANDLE),
    ]


class ProcessInfo(ctypes.Structure):
    _fields_ = [
        ("hProcess", w.HANDLE),
        ("hThread", w.HANDLE),
        ("dwProcessId", w.DWORD),
        ("dwThreadId", w.DWORD),
    ]


def run_standard(executable: Path, output: Path, *, software: bool) -> dict[str, object]:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    security = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
    kernel.WaitForSingleObject.restype = w.DWORD
    kernel.TerminateProcess.argtypes = [w.HANDLE, w.UINT]
    kernel.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
    security.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)]
    security.GetTokenInformation.argtypes = [w.HANDLE, w.DWORD, w.LPVOID, w.DWORD, ctypes.POINTER(w.DWORD)]
    security.CreateRestrictedToken.argtypes = [
        w.HANDLE,
        w.DWORD,
        w.DWORD,
        w.LPVOID,
        w.DWORD,
        w.LPVOID,
        w.DWORD,
        w.LPVOID,
        ctypes.POINTER(w.HANDLE),
    ]
    security.CreateProcessWithTokenW.argtypes = [
        w.HANDLE,
        w.DWORD,
        w.LPCWSTR,
        w.LPWSTR,
        w.DWORD,
        w.LPVOID,
        w.LPCWSTR,
        ctypes.POINTER(StartupInfo),
        ctypes.POINTER(ProcessInfo),
    ]
    security.CreateProcessAsUserW.argtypes = [
        w.HANDLE,
        w.LPCWSTR,
        w.LPWSTR,
        w.LPVOID,
        w.LPVOID,
        w.BOOL,
        w.DWORD,
        w.LPVOID,
        w.LPCWSTR,
        ctypes.POINTER(StartupInfo),
        ctypes.POINTER(ProcessInfo),
    ]

    def require(success: object) -> None:
        if not success:
            raise ctypes.WinError(ctypes.get_last_error())

    def elevated(token: w.HANDLE) -> bool:
        value, size = w.DWORD(), w.DWORD()
        require(
            security.GetTokenInformation(
                token, 20, ctypes.byref(value), ctypes.sizeof(value), ctypes.byref(size)
            )
        )
        return bool(value.value)

    environment = dict(os.environ)
    system_root = os.environ["SYSTEMROOT"]
    environment["PATH"] = os.path.join(system_root, "System32") + ";" + system_root
    for key in tuple(environment):
        if key.upper().startswith(("PYTHON", "QT_", "QML_", "QML2_", "QSG_")):
            environment.pop(key)
    if software:
        environment["QT_QUICK_BACKEND"] = "software"
    arguments = [str(executable), "--smoke-test", str(output)]
    own_token, linked_token, child_token = w.HANDLE(), w.HANDLE(), w.HANDLE()
    process = ProcessInfo()
    child_elevated = True
    try:
        require(security.OpenProcessToken(kernel.GetCurrentProcess(), 0x000B, ctypes.byref(own_token)))
        if not elevated(own_token):
            completed = subprocess.run(
                arguments, cwd=executable.parent, env=environment, timeout=45, check=True
            )
            return {"child_elevated": False, "exit_code": completed.returncode, "token_source": "current"}
        size = w.DWORD()
        token_source = "linked"
        if not security.GetTokenInformation(
            own_token, 19, ctypes.byref(linked_token), ctypes.sizeof(linked_token), ctypes.byref(size)
        ):
            if ctypes.get_last_error() != 1312:
                raise ctypes.WinError(ctypes.get_last_error())
            # UAC-disabled hosts have no linked token. LUA_TOKEN and DISABLE_MAX_PRIVILEGE
            # restrict only this child; they do not alter the account or system settings.
            # https://learn.microsoft.com/windows/win32/api/securitybaseapi/nf-securitybaseapi-createrestrictedtoken
            require(
                security.CreateRestrictedToken(
                    own_token, 0x5, 0, None, 0, None, 0, None, ctypes.byref(linked_token)
                )
            )
            token_source = "restricted-lua"
        if elevated(linked_token):
            raise RuntimeError("Linked token is still elevated")
        startup = StartupInfo()
        startup.cb = ctypes.sizeof(startup)
        startup.lpDesktop = "winsta0\\default"
        block = ctypes.create_unicode_buffer(
            "\0".join(f"{key}={environment[key]}" for key in sorted(environment)) + "\0\0"
        )
        command = ctypes.create_unicode_buffer(subprocess.list2cmdline(arguments))
        if token_source == "restricted-lua":
            require(
                security.CreateProcessAsUserW(
                    linked_token,
                    None,
                    command,
                    None,
                    None,
                    False,
                    0x00000400 | 0x08000000,
                    block,
                    str(executable.parent),
                    ctypes.byref(startup),
                    ctypes.byref(process),
                )
            )
        else:
            require(
                security.CreateProcessWithTokenW(
                    linked_token,
                    0,
                    None,
                    command,
                    0x00000400 | 0x08000000,
                    block,
                    str(executable.parent),
                    ctypes.byref(startup),
                    ctypes.byref(process),
                )
            )
        require(security.OpenProcessToken(process.hProcess, 0x0008, ctypes.byref(child_token)))
        child_elevated = elevated(child_token)
        if child_elevated:
            raise RuntimeError("Portable process unexpectedly elevated")
        if kernel.WaitForSingleObject(process.hProcess, 45000) != 0:
            raise RuntimeError("Standard-user portable smoke timed out")
        code = w.DWORD()
        require(kernel.GetExitCodeProcess(process.hProcess, ctypes.byref(code)))
        if code.value != 0:
            raise RuntimeError(f"Standard-user portable smoke exited with {code.value}")
        return {"child_elevated": child_elevated, "exit_code": code.value, "token_source": token_source}
    finally:
        if process.hProcess and kernel.WaitForSingleObject(process.hProcess, 0) == 258:
            kernel.TerminateProcess(process.hProcess, 1)
            kernel.WaitForSingleObject(process.hProcess, 5000)
        for handle in (child_token, process.hThread, process.hProcess, linked_token, own_token):
            if handle:
                kernel.CloseHandle(handle)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--software", action="store_true")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("This verifier requires Windows")
    args.output.mkdir(parents=True, exist_ok=True)
    report = run_standard(args.executable.resolve(), args.output.resolve(), software=args.software)
    smoke = json.loads((args.output / "smoke-result.json").read_text(encoding="utf-8"))
    report["passed"] = (
        smoke.get("passed") is True
        and smoke.get("version") == args.version
        and smoke.get("exports") == 3
        and smoke.get("qml_errors") == []
        and report["child_elevated"] is False
    )
    report["system_only_path"] = True
    report["backend"] = "software" if args.software else "native"
    (args.output / "standard-user-result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

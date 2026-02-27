import os
import sys
import subprocess
from dataclasses import dataclass

TASK_NAME = "NekoLink_iPhone_Notification_Bridge"

@dataclass
class AutostartResult:
    ok: bool
    message: str

def _run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, shell=False)
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()

def is_enabled() -> bool:
    code, out, err = _run(["schtasks", "/Query", "/TN", TASK_NAME])
    return code == 0

def enable(task_target_path: str) -> AutostartResult:
    """
    task_target_path: exe path OR pythonw + script path command wrapper
    We'll create a task that runs at logon for current user.
    """
    # schtasks needs a single /TR command string
    tr = task_target_path

    cmd = [
        "schtasks", "/Create",
        "/TN", TASK_NAME,
        "/SC", "ONLOGON",
        "/RL", "HIGHEST",
        "/TR", tr,
        "/F"
    ]
    code, out, err = _run(cmd)
    if code == 0:
        return AutostartResult(True, "已启用开机自启动（任务计划）")
    return AutostartResult(False, f"启用失败：{err or out}")

def disable() -> AutostartResult:
    cmd = ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"]
    code, out, err = _run(cmd)
    if code == 0:
        return AutostartResult(True, "已关闭开机自启动（任务计划已删除）")
    return AutostartResult(False, f"关闭失败：{err or out}")

def build_task_command_for_python(script_path: str) -> str:
    """
    Runs GUI without console: pythonw.exe app_gui.py
    """
    py = sys.executable
    # prefer pythonw.exe
    if py.lower().endswith("python.exe"):
        pyw = py[:-9] + "pythonw.exe"
        if os.path.exists(pyw):
            py = pyw
    script_path = os.path.abspath(script_path)
    # quote paths
    return f"\"{py}\" \"{script_path}\""
"""智学路径后端开发启动脚本。"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
VENV_PYTHON = BASE_DIR / ".venv" / ("Scripts" if os.name == "nt" else "bin") / (
    "python.exe" if os.name == "nt" else "python"
)
REEXEC_FLAG = "SLP_VENV_REEXEC"


def ensure_venv() -> None:
    """当前解释器不是项目虚拟环境时，自动切换到 .venv 重新执行。"""
    if os.environ.get(REEXEC_FLAG) == "1":
        return
    if not VENV_PYTHON.exists():
        if not Path(sys.prefix, "pyvenv.cfg").exists():
            print(
                f"未找到虚拟环境 {VENV_PYTHON}，请先创建并安装依赖："
                f"\n  python -m venv .venv"
                f"\n  .venv\\Scripts\\python.exe -m pip install -r requirements.txt",
                file=sys.stderr,
            )
        return

    current = Path(sys.executable).resolve()
    target = VENV_PYTHON.resolve()
    if current == target:
        return

    print(f"检测到未使用虚拟环境，切换解释器：{target}", flush=True)
    os.environ[REEXEC_FLAG] = "1"
    os.execv(str(target), [str(target), *sys.argv])


ensure_venv()

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=[
            ".venv",
            ".uv-cache",
            ".python",
            ".tools",
            "__pycache__",
            "data",
            "*.log",
        ],
    )

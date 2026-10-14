#!/usr/bin/env python3
"""hermes-jailbreak-kernel 离线回归自检（v2.0）—— 无需 Hermes 运行时 / API Key。

用法:
    python selftest.py          # 人类可读（✅/❌ 逐条）
    python selftest.py --json   # JSON 汇总

覆盖（tests/ 模块）：
    test_kernel   内核档：文件存在/锚点/字符预算/双段逐字一致
    test_modes    会话状态机：模式/内核档/轮换/诊断策略/覆盖与复位
    test_harden   请求层：四模式 system 处理、opencode 轮换、诊断落盘
    test_plugin   注册契约与 /jailbreak 命令（mock PluginContext）
    test_i18n     语言目录解析/回退/插值 + 状态报告本地化
    test_docs     技能、docs、manifest、六语言 README 打包完整性
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

MODULES = ["test_kernel", "test_modes", "test_harden", "test_plugin", "test_i18n", "test_docs"]

passes: list[str] = []
failures: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    (passes if ok else failures).append(f"{label}{'' if ok or not detail else ' — ' + detail}")


def main() -> int:
    for name in MODULES:
        try:
            module = importlib.import_module(name)
            module.run(check)
        except Exception as exc:  # 模块级失败不阻断其余模块
            failures.append(f"{name}: 模块执行失败 — {type(exc).__name__}: {exc}")

    if "--json" in sys.argv:
        print(json.dumps({"pass": len(passes), "fail": len(failures),
                          "failures": failures}, ensure_ascii=False, indent=2))
    else:
        for item in passes:
            print(f"  ✅ {item}")
        for item in failures:
            print(f"  ❌ {item}")
        print(f"\n结果: {len(passes)} 通过, {len(failures)} 失败")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

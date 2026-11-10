#!/usr/bin/env python3
"""يبني صفحة وحدة الوكلاء بحقن agents/*.md حرفياً (prompt = محتوى الملف). الاستخدام: build_console.py OUT.html"""
import json, pathlib, sys
root = pathlib.Path(__file__).resolve().parent.parent
agents = {n: (root / "agents" / (n + ".md")).read_text(encoding="utf-8") for n in ("critic", "integrity", "verifier")}
tpl = (root / "tools" / "agents_console_template.html").read_text(encoding="utf-8")
assert "/*AGENTS*/{}" in tpl
payload = json.dumps(agents, ensure_ascii=False).replace("</", "<\\/")
out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "agents_console.html")
out.write_text(tpl.replace("/*AGENTS*/{}", payload), encoding="utf-8")
print(out, out.stat().st_size, "bytes")

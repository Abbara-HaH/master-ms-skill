#!/usr/bin/env python3
"""تحقق من أن أجزاء الدليل (references/guide/G*.md) تعيد تكوين الأصل بايتاً ببايت.
الاستخدام:  python3 scripts/guide_verify.py [مجلد_الحزمة]
يقرأ MANIFEST.json (hash الأصل، وترتيب الأجزاء، وhash كل جزء) ويعيد التجميع والمقارنة.
"""
import hashlib, json, sys, pathlib

root = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(__file__).resolve().parent.parent
gdir = root / "references" / "guide"
man = json.loads((gdir / "MANIFEST.json").read_text(encoding="utf-8"))
blob = b""
ok = True
for p in man["parts"]:
    b = (gdir / p["file"]).read_bytes()
    h = hashlib.sha256(b).hexdigest()
    if h != p["sha256"]:
        print(f"FAIL part hash: {p['file']}"); ok = False
    blob += b
total = hashlib.sha256(blob).hexdigest()
if total != man["original_sha256"]:
    print("FAIL assembled hash", total, "!=", man["original_sha256"]); ok = False
print("OK: الأجزاء تطابق الأصل" if ok else "MISMATCH")
sys.exit(0 if ok else 1)

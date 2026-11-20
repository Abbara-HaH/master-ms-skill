#!/usr/bin/env python3
"""فحص عقود وكلاء ma-thesis بصيغة JSON ثابتة دون تشغيل خدمة خارجية."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

def require_keys(obj, keys, where):
    missing = [key for key in keys if key not in obj]
    if missing:
        raise ValueError("%s: مفاتيح مفقودة: %s" % (where, "، ".join(missing)))


def validate_verifier(obj):
    require_keys(obj, ["status", "checks", "record", "fields", "reason", "alternatives", "could_not_verify"], "verifier")
    if obj["status"] not in ("verified", "partial", "needs_user_text", "unverifiable", "rejected", "candidate"):
        raise ValueError("verifier: status غير معروف")
    require_keys(obj["checks"], ["V1", "V2", "V3", "V4", "V5", "V6"], "verifier.checks")


def validate_critic(obj):
    require_keys(obj, ["objections", "reply_assessments", "chain_gaps", "could_not_assess"], "critic")
    for item in obj["objections"]:
        require_keys(item, ["id", "severity", "criterion", "failure_mode", "where", "evidence", "problem", "what_would_resolve"], "critic.objection")
        if item["severity"] not in ("critical", "major", "minor"):
            raise ValueError("critic: severity غير معروف")


def validate_integrity(obj):
    require_keys(obj, ["verdict", "findings", "chain", "counts", "could_not_check"], "integrity")
    if obj["verdict"] not in ("CLEAR", "SUSPECTED", "BLOCKED"):
        raise ValueError("integrity: verdict غير معروف")
    for item in obj["findings"]:
        require_keys(item, ["mode", "severity", "where", "evidence", "reason", "needs"], "integrity.finding")
        if item["mode"] not in ("M1", "M2", "M3", "M4", "M5", "M6", "M7", "T1"):
            raise ValueError("integrity: mode غير معروف")


CASES = [
    ("verifier", {
        "status": "unverifiable", "checks": {key: {"ok": False, "note": ""} for key in ("V1", "V2", "V3", "V4", "V5", "V6")},
        "record": {"title": "", "authors": [], "year": 0, "venue": "", "doi": "", "pdf_url": "", "access": "open", "type": "journal"},
        "fields": {key: {"text": "", "page": ""} for key in ("goal", "method", "sample", "instrument", "results", "conclusion")},
        "reason": "لم يتحقق من وجود المصدر", "alternatives": [], "could_not_verify": ["نص المصدر"]
    }, validate_verifier),
    ("critic", {
        "objections": [{"id": "O1", "severity": "major", "criterion": 6, "failure_mode": None,
                        "where": "الفصل الرابع", "evidence": "بيان تجريبي غير موثق",
                        "problem": "الإجراء غير مثبت", "what_would_resolve": "إقرار الباحث بالإجراء"}],
        "reply_assessments": [], "chain_gaps": [], "could_not_assess": []
    }, validate_critic),
    ("integrity", {
        "verdict": "SUSPECTED",
        "findings": [{"mode": "M3", "severity": "suspect", "where": "الفصل الخامس",
                      "evidence": "نسبة غير مسجلة", "reason": "لا يوجد إدخال رقمي موثق", "needs": "data_registry"}],
        "chain": [{"link": "الأهداف→الأسئلة", "ok": True, "gap": ""}],
        "counts": {"citations_checked": 0, "numbers_checked": 1, "claims_checked": 0},
        "could_not_check": ["المصادر غير متوفرة"]
    }, validate_integrity),
]

def main():
    failures = []
    for name, obj, checker in CASES:
        try:
            checker(obj)
            json.dumps(obj, ensure_ascii=False)
        except (ValueError, TypeError) as e:
            failures.append("%s: %s" % (name, e))
    if failures:
        print("\n".join("FAIL " + item for item in failures), file=sys.stderr)
        return 1
    print("VALID: verifier, critic, integrity contracts")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

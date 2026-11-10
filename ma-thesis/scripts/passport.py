#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""passport.py — «الجواز»: حالة المشروع في شظايا JSON تُقرأ بالمفتاح (اقتصاد التوكن).

الاستخدام:  passport.py [--dir passport] COMMAND ...
  init  --title T --type quantitative|qualitative|mixed|theoretical [--discipline D]
  show                                  ملخص الفهرس فقط
  meta  [--set key=value ...]           قراءة/تعديل بيانات الفهرس (stage, title, ...)
  read  FRAG [--key K]                  قراءة شظية أو مفتاح منها
  write FRAG --key K --value JSON [--expect-version N]
  del   FRAG --key K [--expect-version N]
  append FRAG --value JSON [--expect-version N]     للقوائم (decisions, corrections_log, audit_log)
  draft save NAME --file F [--note N] | list | get NAME [--version N]
  validate                              يفحص الهاش والمخطط والادعاءات (رمز خروج 1 عند الفشل)
  rehash --confirm                      يقبل تعديلاً يدوياً (يُسجَّل في audit_log)
  pack OUT.zip [--force]   |   unpack ZIP --dir DIR [--force]

رموز الخروج: 0 نجاح، 1 فشل تحقق، 2 خطأ استخدام، 3 تعارض إصدار.
الجواز لا يحوي كلمات مرور ولا بيانات شخصية للمستجيبين؛ المعطيات الطويلة تُلخَّص ويبقى الأصل ملفاً مستقلاً.
"""
import argparse, contextlib, datetime, hashlib, json, os, pathlib, re, sys, tempfile, time, zipfile

SCHEMA = 1
FRAGMENTS = {  # اسم → نوع الحاوية
    "sources": dict, "lit_cards": dict, "claims": dict, "decisions": list, "style_profile": dict,
    "learned_rules": dict, "corrections_log": list, "data_registry": dict, "audit_log": list,
}
SOURCE_STATUS = {"verified", "partial", "needs_user_text", "unverifiable", "rejected", "candidate"}
STAGES = ["S0", "S1", "S2", "S3", "S4", "S5", "G-A", "S6", "S7", "S8", "G-B", "S9"]
FORBIDDEN_KEY = re.compile(r"(password|passwd|secret|api[_-]?key|token|كلمة[\s_]?(?:ال)?مرور)", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?<!\d)\+?\d[\d\s\-]{8,}\d(?!\d)")
NAME_OK = re.compile(r"^[\w\u0600-\u06FF.\-]{1,80}$")


# سياسة المصدر (H7). المصدر: GUIDE_INDEX R01–R04؛ التشديد من الأداة [اجتهاد].
BLOCKED_HOSTS = re.compile(r"wikipedia|wikiwand|wikimedia|wikihow|blogspot\.|wordpress\.com|medium\.com|quora\.com|scribd\.com|"
                           r"facebook\.com|twitter\.com|(?:/|\.)x\.com(?:/|$)|youtube\.com|youtu\.be|pinterest\.|tumblr\.com|mawdoo3|marefa\.org", re.I)
ALLOWED_CLASS = {"university", "research_center", "official", "international", "journal", "publisher", "conference"}
ACADEMIC_TYPES = {"journal", "book", "thesis", "conference", "report"}


def policy_problems(s):
    """يعيد قائمة أسباب حجب H7 لمصدر (فارغة = لا مانع). المرجع: G14:1402–1407."""
    out = []
    url = " ".join(str(s.get(k, "")) for k in ("url", "pdf_url", "landing_url"))
    if BLOCKED_HOSTS.search(url) or "ويكيبيديا" in str(s.get("title", "")) + str(s.get("venue", "")):
        out.append("موسوعة إلكترونية/موقع غير مؤسسي (H7)")
    if s.get("type") == "thesis" and str(s.get("thesis_level", "")).lower() in ("diploma", "دبلوم"):
        out.append("رسالة دبلوم في مستوى الماجستير (H7)")
    if s.get("type") in ("school_textbook", "textbook_school") and not s.get("is_case_studied"):
        out.append("كتاب تعليم مدرسي وليس الحالة المدروسة (H7)")
    if s.get("type") == "web" and s.get("publisher_class") not in ALLOWED_CLASS - {"journal", "publisher", "conference"}:
        out.append("موقع ويب ناشره ليس جامعة/مركز أبحاث/جهة رسمية/دولية (H7: publisher_class=%s)" % s.get("publisher_class"))
    return out


class PassportError(Exception):
    def __init__(self, msg, code=2):
        super().__init__(msg); self.code = code


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha(b):
    return hashlib.sha256(b).hexdigest()


def dump(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode("utf-8")


def atomic_write(path, data):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise


@contextlib.contextmanager
def lock(root):
    if not pathlib.Path(root).is_dir():
        raise PassportError("المجلد غير موجود: %s" % root)
    lp = pathlib.Path(root) / ".lock"
    for _ in range(100):
        try:
            fd = os.open(str(lp), os.O_CREAT | os.O_EXCL | os.O_WRONLY); os.close(fd); break
        except FileExistsError:
            if time.time() - lp.stat().st_mtime > 30:  # قفل قديم
                with contextlib.suppress(FileNotFoundError):
                    lp.unlink()
            time.sleep(0.05)
    else:
        raise PassportError("تعذّر الحصول على القفل", 3)
    try:
        yield
    finally:
        with contextlib.suppress(FileNotFoundError):
            lp.unlink()


class Passport:
    def __init__(self, root):
        self.root = pathlib.Path(root)

    @property
    def ipath(self):
        return self.root / "index.json"

    def index(self):
        if not self.ipath.exists():
            raise PassportError("لا جواز في %s (نفّذ init)" % self.root)
        try:
            return json.loads(self.ipath.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise PassportError("index.json تالف: %s" % e, 1)

    def save_index(self, idx):
        idx["updated"] = now()
        atomic_write(self.ipath, dump(idx))

    def frag_path(self, name):
        if name not in FRAGMENTS:
            raise PassportError("شظية غير معروفة: %s (المتاح: %s)" % (name, "، ".join(FRAGMENTS)))
        return self.root / (name + ".json")

    def load(self, name):
        p = self.frag_path(name)
        if not p.exists():
            return FRAGMENTS[name]()
        return json.loads(p.read_text(encoding="utf-8"))

    def store(self, idx, name, obj, expect_version=None):
        cur = idx["fragments"].get(name, {"version": 0})
        if expect_version is not None and cur["version"] != expect_version:
            raise PassportError("تعارض إصدار في %s: المتوقع %s والحالي %s" % (name, expect_version, cur["version"]), 3)
        self.check_clean(name, obj)
        data = dump(obj)
        atomic_write(self.frag_path(name), data)
        idx["fragments"][name] = {"sha256": sha(data), "version": cur["version"] + 1, "bytes": len(data), "updated": now()}

    def log(self, idx, action, detail):
        if "audit_log" not in idx["fragments"] and not (self.root / "audit_log.json").exists():
            lst = []
        else:
            lst = self.load("audit_log")
        lst.append({"t": now(), "action": action, "detail": detail})
        self.store(idx, "audit_log", lst)

    @staticmethod
    def check_clean(name, obj):
        """لا كلمات مرور ولا بيانات شخصية: يُرفض عند الكتابة لا عند التحقق فقط."""
        def walk(x, path=""):
            if isinstance(x, dict):
                for k, v in x.items():
                    if FORBIDDEN_KEY.search(str(k)):
                        raise PassportError("مفتاح محظور (%s%s): الجواز لا يحوي أسراراً" % (path, k), 1)
                    walk(v, path + str(k) + ".")
            elif isinstance(x, list):
                for i, v in enumerate(x):
                    walk(v, path + "%d." % i)
            elif isinstance(x, str) and name in ("data_registry", "decisions", "claims"):
                if EMAIL.search(x):
                    raise PassportError("بريد إلكتروني في %s: ممنوع حفظ بيانات المستجيبين" % name, 1)
        walk(obj)


# ----------------------------------------------------------------- الأوامر
def cmd_init(p, a):
    p.root.mkdir(parents=True, exist_ok=True)
    if p.ipath.exists():
        raise PassportError("الجواز موجود؛ لن يُستبدل")
    idx = {"schema": SCHEMA, "title": a.title, "study_type": a.type, "discipline": a.discipline or "", "stage": "S0",
           "created": now(), "updated": now(), "fragments": {}, "drafts": [], "gates": {}, "notes": {}}
    with lock(p.root):
        for n, t in FRAGMENTS.items():
            p.store(idx, n, t())
        p.log(idx, "init", {"title": a.title, "type": a.type})
        p.save_index(idx)
    (p.root / "drafts").mkdir(exist_ok=True)
    print("تم إنشاء الجواز:", p.root)


def cmd_show(p, a):
    idx = p.index()
    print(json.dumps({k: idx[k] for k in ("schema", "title", "study_type", "discipline", "stage", "updated", "gates", "notes")}, ensure_ascii=False, indent=1))
    print("الشظايا:", {n: "v%d" % f["version"] for n, f in idx["fragments"].items()})
    print("المسودات:", [(d["name"], "v%d" % d["version"]) for d in idx["drafts"]])


def cmd_meta(p, a):
    with lock(p.root):
        idx = p.index()
        for kv in a.set or []:
            k, _, v = kv.partition("=")
            if k == "stage" and v not in STAGES:
                raise PassportError("مرحلة غير معروفة: %s (%s)" % (v, "، ".join(STAGES)))
            if k in ("title", "study_type", "discipline", "stage"):
                idx[k] = v
            elif k.startswith("gate."):
                idx["gates"][k[5:]] = v
            elif k.startswith("note."):
                idx["notes"][k[5:]] = v
            else:
                raise PassportError("مفتاح غير مسموح: " + k)
        if a.set:
            p.log(idx, "meta", a.set)
            p.save_index(idx)
    print(json.dumps({k: idx[k] for k in ("title", "study_type", "discipline", "stage", "gates", "notes")}, ensure_ascii=False, indent=1))


def cmd_read(p, a):
    idx = p.index()
    obj = p.load(a.frag)
    if a.key is not None:
        if isinstance(obj, dict):
            if a.key not in obj:
                raise PassportError("المفتاح غير موجود: " + a.key, 1)
            obj = obj[a.key]
        else:
            raise PassportError("الشظية قائمة؛ اقرأها كاملة")
    print(json.dumps(obj, ensure_ascii=False, indent=1))
    print("# version=%s sha256=%s" % (idx["fragments"].get(a.frag, {}).get("version"), idx["fragments"].get(a.frag, {}).get("sha256", "")[:12]), file=sys.stderr)


def parse_value(s):
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        raise PassportError("القيمة ليست JSON صالحاً")


def cmd_write(p, a):
    if FRAGMENTS.get(a.frag) is not dict:
        raise PassportError("write للشظايا المفتاحية فقط؛ استعمل append للقوائم")
    with lock(p.root):
        idx = p.index()
        obj = p.load(a.frag)
        val = parse_value(a.value)
        if a.frag in ("sources", "claims", "lit_cards", "learned_rules") and not isinstance(val, dict):
            raise PassportError("قيمة %s يجب أن تكون كائن JSON" % a.frag)
        if a.frag == "sources":
            st = val.get("status") if isinstance(val, dict) else None
            if st not in SOURCE_STATUS:
                raise PassportError("حالة المصدر يجب أن تكون إحدى: " + "، ".join(sorted(SOURCE_STATUS)))
            if st == "verified":
                miss = [k for k in ("title", "authors", "year", "pdf_url", "evidence_pages") if not val.get(k)]
                if miss:
                    raise PassportError("verified يتطلب (H1): " + "، ".join(miss), 1)
                pp = policy_problems(val)
                if pp:
                    raise PassportError("لا يُقبل verified: " + "؛ ".join(pp) + " — استعمل rejected مع السبب", 1)
        obj[a.key] = val
        p.store(idx, a.frag, obj, a.expect_version)
        p.log(idx, "write", {"frag": a.frag, "key": a.key})
        p.save_index(idx)
    print("كُتب %s[%s]" % (a.frag, a.key))


def cmd_del(p, a):
    if FRAGMENTS.get(a.frag) is not dict:
        raise PassportError("del للشظايا المفتاحية فقط")
    with lock(p.root):
        idx = p.index()
        obj = p.load(a.frag)
        if a.key not in obj:
            raise PassportError("المفتاح غير موجود: " + a.key, 1)
        del obj[a.key]
        p.store(idx, a.frag, obj, a.expect_version)
        p.log(idx, "del", {"frag": a.frag, "key": a.key})
        p.save_index(idx)
    print("حُذف %s[%s]" % (a.frag, a.key))


def cmd_append(p, a):
    if FRAGMENTS.get(a.frag) is not list:
        raise PassportError("append للقوائم فقط (decisions, corrections_log, audit_log)")
    with lock(p.root):
        idx = p.index()
        obj = p.load(a.frag)
        obj.append(parse_value(a.value))
        p.store(idx, a.frag, obj, a.expect_version)
        if a.frag != "audit_log":
            p.log(idx, "append", {"frag": a.frag})
        p.save_index(idx)
    print("أُضيف إلى", a.frag)


def cmd_draft(p, a):
    if a.sub == "list":
        print(json.dumps(p.index()["drafts"], ensure_ascii=False, indent=1)); return
    if not NAME_OK.match(a.name or ""):
        raise PassportError("اسم مسودة غير صالح")
    with lock(p.root):
        idx = p.index()
        if a.sub == "save":
            data = pathlib.Path(a.file).read_bytes()
            ver = 1 + max([d["version"] for d in idx["drafts"] if d["name"] == a.name] or [0])
            fn = "drafts/%s.v%d.md" % (a.name, ver)
            atomic_write(p.root / fn, data)
            idx["drafts"].append({"name": a.name, "version": ver, "file": fn, "sha256": sha(data), "saved": now(), "note": a.note or ""})
            p.log(idx, "draft_save", {"name": a.name, "version": ver})
            p.save_index(idx)
            print("حُفظت", fn)
        elif a.sub == "get":
            c = [d for d in idx["drafts"] if d["name"] == a.name and (a.version is None or d["version"] == a.version)]
            if not c:
                raise PassportError("مسودة غير موجودة", 1)
            d = max(c, key=lambda d: d["version"])
            sys.stdout.write((p.root / d["file"]).read_text(encoding="utf-8"))


def validate(p):
    errs, warns = [], []
    try:
        idx = p.index()
    except PassportError as e:
        return [str(e)], []
    if idx.get("schema") != SCHEMA:
        errs.append("إصدار مخطط غير مدعوم: %s (المدعوم %s)؛ لا تُصلح الشظايا يدوياً دون تأكيد" % (idx.get("schema"), SCHEMA))
    loaded = {}
    for n in FRAGMENTS:
        meta = idx.get("fragments", {}).get(n)
        path = p.root / (n + ".json")
        if not meta:
            errs.append("شظية غائبة من الفهرس: " + n); continue
        if not path.exists():
            errs.append("ملف الشظية مفقود: %s.json" % n); continue
        b = path.read_bytes()
        if sha(b) != meta["sha256"]:
            errs.append("هاش غير مطابق (تعديل خارج الأداة؟): %s.json" % n)
        try:
            loaded[n] = json.loads(b.decode("utf-8"))
        except Exception as e:
            errs.append("JSON تالف في %s.json: %s" % (n, e)); continue
        if not isinstance(loaded[n], FRAGMENTS[n]):
            errs.append("نوع غير متوقع في " + n)
        else:
            try:
                Passport.check_clean(n, loaded[n])
            except PassportError as e:
                errs.append("%s: %s" % (n, e))
    for d in idx.get("drafts", []):
        f = p.root / d["file"]
        if not f.exists():
            errs.append("مسودة مفقودة: " + d["file"])
        elif sha(f.read_bytes()) != d["sha256"]:
            errs.append("هاش مسودة غير مطابق: " + d["file"])
    src = loaded.get("sources", {})
    src = {k: v for k, v in src.items() if isinstance(v, dict)}
    for sid, s in src.items():
        if s.get("status") not in SOURCE_STATUS:
            errs.append("مصدر %s بحالة غير معروفة: %s" % (sid, s.get("status")))
        if s.get("status") == "verified":
            miss = [k for k in ("title", "authors", "year", "pdf_url", "evidence_pages") if not s.get(k)]
            if miss:
                errs.append("مصدر %s verified لكن ينقصه (H1): %s" % (sid, "، ".join(miss)))
            for why in policy_problems(s):
                errs.append("مصدر %s verified يخالف سياسة المصادر: %s" % (sid, why))
    for frag in ("sources", "claims", "lit_cards", "learned_rules"):
        for k, v in list(loaded.get(frag, {}).items()):
            if not isinstance(v, dict):
                errs.append("%s[%s] ليس كائناً" % (frag, k))
                loaded[frag].pop(k)
    for cid, c in loaded.get("claims", {}).items():
        if c.get("status") == "rejected":      # ادعاء مرفوض: مُسجَّل للتتبع ولا يدخل النص؛ يُشترط السبب
            if not c.get("reason"):
                errs.append("ادعاء مرفوض %s بلا سبب" % cid)
            continue
        kind = c.get("kind", "cited")
        ids = c.get("source_ids", [])
        if kind == "cited":
            if not ids:
                errs.append("ادعاء %s منسوب بلا مصدر" % cid)
            for sid in ids:
                if sid not in src:
                    errs.append("ادعاء %s يشير إلى مصدر غير موجود: %s" % (cid, sid))
                elif src[sid].get("status") != "verified":
                    errs.append("ادعاء %s يشير إلى مصدر غير verified (%s: %s) — H1" % (cid, sid, src[sid].get("status")))
            if not c.get("page"):
                errs.append("ادعاء %s بلا رقم صفحة (H1-ج)" % cid)
        elif kind == "data":
            if c.get("data_ref") not in loaded.get("data_registry", {}):
                errs.append("ادعاء رقمي %s بلا بيانات مسجَّلة في data_registry — H2" % cid)
        elif kind != "own":
            warns.append("ادعاء %s بنوع غير معروف: %s" % (cid, kind))
    for lid, r in loaded.get("learned_rules", {}).items():
        if not r.get("approved_by_user"):
            errs.append("قاعدة متعلَّمة %s بلا موافقة الباحث (approved_by_user)" % lid)
    for cid, c in loaded.get("lit_cards", {}).items():
        if c.get("source_id") not in src:
            errs.append("بطاقة دراسة %s بمصدر غير موجود" % cid)
    return errs, warns


def cmd_validate(p, a):
    errs, warns = validate(p)
    for w in warns:
        print("تحذير:", w)
    for e in errs:
        print("فشل:", e)
    print("VALID" if not errs else "INVALID (%d)" % len(errs))
    return 1 if errs else 0


def cmd_rehash(p, a):
    if not a.confirm:
        raise PassportError("أضف --confirm: إعادة الهاش تقبل التعديل اليدوي وتُسجَّل")
    with lock(p.root):
        idx = p.index()
        changed = []
        for n in FRAGMENTS:
            f = p.root / (n + ".json")
            if f.exists():
                b = f.read_bytes()
                try:
                    obj = json.loads(b.decode("utf-8"))
                except Exception as e:
                    raise PassportError("لا يمكن إعادة هاش %s: JSON تالف (%s)" % (n, e), 1)
                if idx["fragments"].get(n, {}).get("sha256") != sha(b):
                    m = idx["fragments"].setdefault(n, {"version": 0})
                    m.update({"sha256": sha(b), "version": m["version"] + 1, "bytes": len(b), "updated": now()})
                    changed.append(n)
        for d in idx["drafts"]:
            f = p.root / d["file"]
            if f.exists() and sha(f.read_bytes()) != d["sha256"]:
                d["sha256"] = sha(f.read_bytes()); changed.append(d["file"])
        p.log(idx, "rehash", changed)
        p.save_index(idx)
    print("أُعيد هاش:", changed or "لا تغيير")


def cmd_pack(p, a):
    errs, _ = validate(p)
    if errs and not a.force:
        for e in errs:
            print("فشل:", e)
        raise PassportError("الجواز غير صالح؛ أصلحه أو استعمل --force", 1)
    idx = p.index()
    out = pathlib.Path(a.out)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(p.ipath, "index.json")
        for n in FRAGMENTS:
            f = p.root / (n + ".json")
            if f.exists():
                z.write(f, n + ".json")
        for d in idx["drafts"]:
            f = p.root / d["file"]
            if f.exists():
                z.write(f, d["file"])
    print("حُزم:", out, "(%d بايت)" % out.stat().st_size)


def safe_member(name):
    if name.startswith(("/", "\\")) or ".." in pathlib.PurePosixPath(name).parts or ":" in name or "\\" in name:
        return False
    if name == "index.json":
        return True
    if re.fullmatch(r"[a-z_]+\.json", name) and name[:-5] in FRAGMENTS:
        return True
    return bool(re.fullmatch(r"drafts/[\w\u0600-\u06FF.\-]{1,100}\.md", name))


def cmd_unpack(p, a):
    target = pathlib.Path(a.dir).resolve()
    if target.exists() and any(target.iterdir()) and not a.force:
        raise PassportError("المجلد الهدف غير فارغ (استعمل --force)")
    with zipfile.ZipFile(a.zip) as z:
        names = z.namelist()
        bad = [n for n in names if not safe_member(n)]
        if bad:
            raise PassportError("ملفات مرفوضة في الأرشيف (zip-slip أو اسم غير مسموح): %s" % bad[:5], 1)
        for n in names:
            dest = (target / n).resolve()
            if target not in dest.parents and dest != target:
                raise PassportError("مسار خارج الهدف: " + n, 1)
        target.mkdir(parents=True, exist_ok=True)
        for n in names:
            if n.endswith("/"):
                continue
            atomic_write(target / n, z.read(n))
    q = Passport(target)
    errs, warns = validate(q)
    for e in errs:
        print("فشل:", e)
    print("فُتح في", target, "VALID" if not errs else "INVALID (%d)" % len(errs))
    return 1 if errs else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default="passport")
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("init"); s.add_argument("--title", required=True); s.add_argument("--type", required=True, choices=["quantitative", "qualitative", "mixed", "theoretical"]); s.add_argument("--discipline")
    sp.add_parser("show")
    s = sp.add_parser("meta"); s.add_argument("--set", action="append")
    s = sp.add_parser("read"); s.add_argument("frag"); s.add_argument("--key")
    s = sp.add_parser("write"); s.add_argument("frag"); s.add_argument("--key", required=True); s.add_argument("--value", required=True); s.add_argument("--expect-version", type=int)
    s = sp.add_parser("del"); s.add_argument("frag"); s.add_argument("--key", required=True); s.add_argument("--expect-version", type=int)
    s = sp.add_parser("append"); s.add_argument("frag"); s.add_argument("--value", required=True); s.add_argument("--expect-version", type=int)
    s = sp.add_parser("draft"); s.add_argument("sub", choices=["save", "list", "get"]); s.add_argument("name", nargs="?"); s.add_argument("--file"); s.add_argument("--note"); s.add_argument("--version", type=int)
    sp.add_parser("validate")
    s = sp.add_parser("rehash"); s.add_argument("--confirm", action="store_true")
    s = sp.add_parser("pack"); s.add_argument("out"); s.add_argument("--force", action="store_true")
    s = sp.add_parser("unpack"); s.add_argument("zip"); s.add_argument("--force", action="store_true")
    s.add_argument("--dir", dest="dir", required=True)
    a = ap.parse_args()
    # unpack يستعمل --dir كمجلد هدف لا كمجلد الجواز
    p = Passport(a.dir if a.cmd != "unpack" else ".")
    fn = {"init": cmd_init, "show": cmd_show, "meta": cmd_meta, "read": cmd_read, "write": cmd_write, "del": cmd_del, "append": cmd_append,
          "draft": cmd_draft, "validate": cmd_validate, "rehash": cmd_rehash, "pack": cmd_pack, "unpack": cmd_unpack}[a.cmd]
    try:
        return fn(p, a) or 0
    except PassportError as e:
        print("خطأ:", e, file=sys.stderr); return e.code
    except FileNotFoundError as e:
        print("خطأ: ملف غير موجود:", e.filename, file=sys.stderr); return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:  # مثل `| head`
        sys.exit(0)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""format_check.py — فحص التنسيق والهيكل بأرقام الدليل (لا بأرقام من خارجه).

الاستخدام:
  format_check.py FILE [--kind thesis|plan|abstract] [--title "العنوان"] [--registry data_registry.json] [--json]

الأرقام (المرجع: references/rules_core.md وملفات الدليل):
  العنوان ≤ 15 كلمة (G05:357) · الملخص ≤ 400 كلمة، فقرة واحدة، كلمات مفتاحية ≤ 8، بلا استشهادات/جداول (G04)
  الفصول ≤ 5 (G04:246) · الإجمالي ≤ 30000 كلمة (G03:160) · الإطار النظري ≤ 25% (G09:754)
  المقدمة ≤ صفحتين (G06:391) · المخطط 14 عنصراً بترتيبه، 7–15 صفحة (G15:1480–1497)
  ترقيم الجداول/الأشكال متسلسل (G13:1282، 1307) · اقتباس حرفي برقم صفحة (G14:1339) · مطابقة المتن مع المراجع
[اجتهاد]: تقدير الصفحات من الكلمات (WORDS_PER_PAGE) تقريبي؛ الصفحات الحقيقية تُقاس في Word.
الخروج: 1 عند أي ERROR، 0 غير ذلك، 2 خطأ في المدخلات.
"""
import argparse, json, pathlib, re, sys

AR = r"\u0621-\u064A"
DIAC = re.compile("[\u064B-\u0652\u0670\u0640]")
WORDS_PER_PAGE = 250  # [اجتهاد] خط 14، تباعد 1.5، هوامش 2.54
LIMITS = {"title_words": 15, "abstract_words": 400, "keywords": 8, "chapters": 5, "total_words": 30000,
          "theory_ratio": 0.25, "intro_pages": 2, "plan_pages": (7, 15), "pages": (40, 80), "quote_words": 15}
MODEL3 = ["الاطار المنهجي", "دراسات سابقة", "الاطار النظري", "الاطار العملي", "عرض النتائج"]
PLAN14 = ["مقدمة", "مشكلة", "اهمية", "اهداف", "اسئلة", "متغيرات", "فرضيات", "حدود", "ادوات", "المجتمع", "مصطلحات",
          "دراسات سابقة", "التعقيب", "المراجع"]
CIT = re.compile(r"\(([^()\n]*?)[،,]\s*((?:19|20)\d{2})(?:[،,]\s*([^()\n]*?))?\)")
NARR = re.compile(r"([\u0621-\u064A]+(?:\s+و[\u0621-\u064A]+)?(?:\s+وآخرين)?)\s*\(\s*((?:19|20)\d{2})\s*\)(?:[^()\n]{0,200}?\(\s*ص\s*[\d\-–]+\s*\))?")
QUOTE = re.compile(r"«([^»]{1,600})»|“([^”]{1,600})”|\"([^\"\n]{1,600})\"")
PLACE = re.compile(r"\[(?:الباحث|ادخل النتيجة|أدخل النتيجة|يحتاج مصدراً|يحتاج مصدرا|مقترح آلي)[^\]]*\]")


def norm(t):
    t = DIAC.sub("", t)
    for a in "أإآٱ":
        t = t.replace(a, "ا")
    return t.replace("ى", "ي")


def words(t):
    return re.findall(r"[" + AR + r"0-9A-Za-z]+", t)


def strip_md(t):
    t = re.sub(r"^```.*?^```", "", t, flags=re.S | re.M)
    t = re.sub(r"^\s*\|.*$", "", t, flags=re.M)
    t = re.sub(r"^\s*#{1,6}\s*", "", t, flags=re.M)
    t = PLACE.sub("", t)
    return re.sub(r"[*_>`]", "", t)


def sections(text):
    """قائمة (مستوى، عنوان، نص_القسم_حتى_العنوان_التالي)."""
    parts, cur = [], None
    for line in text.split("\n"):
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            if cur:
                parts.append(cur)
            cur = [len(m.group(1)), m.group(2).strip(), []]
        elif cur is not None:
            cur[2].append(line)
    if cur:
        parts.append(cur)
    return [(l, h, "\n".join(b)) for l, h, b in parts]


class Rep:
    def __init__(self):
        self.items = []

    def add(self, level, check, msg, ref=""):
        self.items.append({"level": level, "check": check, "msg": msg, "ref": ref})


def check_title(text, title, rep):
    if not title:
        m = re.search(r"^#\s+(.+)$", text, re.M)
        title = m.group(1).strip() if m else None
    if not title:
        rep.add("WARN", "العنوان", "لم يُعثر على عنوان (سطر # أو --title)", "G05:357"); return
    n = len(words(title))
    rep.add("ERROR" if n > LIMITS["title_words"] else "OK", "العنوان",
            "%d كلمة (الحد %d)" % (n, LIMITS["title_words"]), "G05:357")


def check_abstract(text, rep):
    secs = [s for s in sections(text) if "ملخص" in norm(s[1]) and "الاجنبية" not in norm(s[1]) and "اجنبي" not in norm(s[1])]
    if not secs:
        rep.add("WARN", "الملخص", "لا قسم «ملخص» في الملف", "G04:305"); return
    body = secs[0][2]
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    kw = [p for p in paras if norm(p).startswith("الكلمات المفتاحية")]
    prose = [p for p in paras if p not in kw and not p.startswith("|") and len(words(p)) > 25]
    if len(prose) != 1:
        rep.add("ERROR", "الملخص", "يجب فقرة واحدة؛ وُجد %d فقرات نثرية طويلة" % len(prose), "G04:311")
    if prose:
        n = len(words(strip_md(prose[0])))
        rep.add("ERROR" if n > LIMITS["abstract_words"] else "OK", "الملخص", "%d كلمة (الحد %d)" % (n, LIMITS["abstract_words"]), "G04:311")
        if CIT.search(prose[0]) or NARR.search(prose[0]):
            rep.add("ERROR", "الملخص", "يحتوي استشهاداً؛ الملخص بلا مراجع", "G04:317")
    if "|" in body:
        rep.add("ERROR", "الملخص", "يحتوي جدولاً؛ الملخص بلا جداول/أشكال", "G04:317")
    if not kw:
        rep.add("ERROR", "الملخص", "لا سطر «الكلمات المفتاحية»", "G04:313")
    else:
        k = re.sub(r"^[^:：]*[:：]", "", kw[0])
        ks = [x for x in re.split(r"[،,]", k) if x.strip()]
        rep.add("ERROR" if len(ks) > LIMITS["keywords"] else "OK", "الملخص", "%d كلمة مفتاحية (الحد %d، يفصل بينها فاصلة)" % (len(ks), LIMITS["keywords"]), "G04:319")


def check_chapters(text, rep):
    secs = sections(text)
    chap = [s for s in secs if re.match(r"^\s*الفصل", norm(s[1]))]
    if not chap:
        rep.add("WARN", "الفصول", "لا عناوين «الفصل …»", "G04:246"); return
    rep.add("ERROR" if len(chap) > LIMITS["chapters"] else "OK", "الفصول", "%d فصول (الحد %d)" % (len(chap), LIMITS["chapters"]), "G04:246")
    names = [norm(c[1]) for c in chap]
    pos = []
    for m in MODEL3:
        i = next((j for j, n in enumerate(names) if m in n), None)
        pos.append(i)
    present = [p for p in pos if p is not None]
    if present != sorted(present):
        rep.add("ERROR", "ترتيب الفصول", "ترتيب الفصول لا يطابق النموذج (3): " + " ← ".join(MODEL3), "G04:248")
    miss = [m for m, p in zip(MODEL3, pos) if p is None]
    if miss:
        rep.add("WARN", "الفصول", "فصول النموذج (3) غير موجودة بعد: " + "، ".join(miss), "G04:248")
    # الإجمالي والإطار النظري: الفصل = من عنوانه إلى الفصل التالي (مستوى ≤ مستواه)
    total = len(words(strip_md(text)))
    rep.add("ERROR" if total > LIMITS["total_words"] else "OK", "الحجم", "%d كلمة (الحد %d). الصفحات (40–80) تُقاس في Word؛ تقدير تقريبي ≈ %d صفحة [اجتهاد]" % (total, LIMITS["total_words"], round(total / WORDS_PER_PAGE)), "G03:160")
    lines = text.split("\n")
    th_words = 0
    inside = False
    lvl = 0
    for ln in lines:
        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            if re.match(r"^\s*الفصل", norm(m.group(2))):
                inside = "الاطار النظري" in norm(m.group(2)); lvl = len(m.group(1))
            elif inside and len(m.group(1)) <= lvl:
                inside = False
            continue
        if inside:
            th_words += len(words(strip_md(ln)))
    if total:
        r = th_words / total
        rep.add("ERROR" if r > LIMITS["theory_ratio"] else "OK", "الإطار النظري", "%.0f%% من الكلمات (الحد %.0f%% من الصفحات؛ النسبة بالكلمات تقريب)" % (r * 100, LIMITS["theory_ratio"] * 100), "G09:754")
    for l, h, body in secs:
        if "مقدمه" in norm(h).replace("ة", "ه") and len(norm(h)) < 30:
            n = len(words(strip_md(body)))
            lim = LIMITS["intro_pages"] * WORDS_PER_PAGE
            rep.add("WARN" if n > lim else "OK", "المقدمة", "%d كلمة (≈%.1f صفحة؛ الحد صفحتان [تقدير])" % (n, n / WORDS_PER_PAGE), "G06:391")
            break


def check_plan(text, rep):
    secs = [norm(h) for l, h, b in sections(text)]
    pos = []
    for k in PLAN14:
        i = next((j for j, h in enumerate(secs) if k in h and not (k == "مقدمة" and "ملخص" in h)), None)
        pos.append(i)
    miss = [k for k, p in zip(PLAN14, pos) if p is None]
    if miss:
        rep.add("ERROR", "مخطط البحث", "عناصر مفقودة من الـ14: " + "، ".join(miss), "G15:1480")
    present = [p for p in pos if p is not None]
    if present != sorted(present):
        rep.add("ERROR", "مخطط البحث", "ترتيب العناصر لا يطابق قائمة المخطط (G15:1482–1495)", "G15:1480")
    if not miss and present == sorted(present):
        rep.add("OK", "مخطط البحث", "14 عنصراً بالترتيب", "G15:1480")
    n = len(words(strip_md(text)))
    pg = n / WORDS_PER_PAGE
    lo, hi = LIMITS["plan_pages"]
    rep.add("WARN" if (pg < lo or pg > hi) else "OK", "حجم المخطط", "≈ %.1f صفحة (المسموح %d–%d؛ تقدير من %d كلمة [اجتهاد]، يُقاس في Word)" % (pg, lo, hi, n), "G15:1497")


def check_tables_figures(text, rep):
    for kind, pat in (("الجداول", r"جدول\s*\(\s*(\d+)\s*\)"), ("الأشكال", r"الشكل\s*\(\s*(\d+)\s*\)")):
        caps = []
        for ln in text.split("\n"):
            s = ln.strip().lstrip("*").strip()
            m = re.match(pat, s)
            if m:
                caps.append(int(m.group(1)))
        if caps:
            exp = list(range(1, len(caps) + 1))
            rep.add("OK" if caps == exp else "ERROR", "ترقيم " + kind, ("متسلسل 1..%d" % len(caps)) if caps == exp else "غير متسلسل: %s (المتوقع %s)" % (caps, exp), "G13:1282، 1307")
    # الجدول: عنوانه أعلى (سطر الرقم يتبعه جدول)
    ls = text.split("\n")
    for i, ln in enumerate(ls):
        if re.match(r"^\s*\**\s*جدول\s*\(\s*\d+\s*\)", ln):
            nxt = [x for x in ls[i + 1:i + 4] if x.strip()]
            if not (nxt and nxt[0].lstrip().startswith("|")):
                rep.add("WARN", "الجداول", "سطر %d: بعد عنوان الجدول لا يأتي الجدول مباشرة (العنوان أعلى الجدول)" % (i + 1), "G13:1283")


def check_quotes(text, rep):
    t = re.sub(r"^\s*\|.*$", "", text, flags=re.M)
    bad_page, too_long = [], []
    for m in QUOTE.finditer(t):
        q = next(g for g in m.groups() if g)
        if len(words(q)) < 3:
            continue
        tail = t[m.end(): m.end() + 60]
        if len(words(q)) >= LIMITS["quote_words"]:
            too_long.append(q[:40])
        if not re.search(r"\(\s*ص\s*\d|[،,]\s*\d{1,4}\s*\)|\(\s*[^()]*?(?:19|20)\d{2}[،,]\s*\d", tail):
            bad_page.append(q[:40])
    rep.add("ERROR" if bad_page else "OK", "الاقتباسات", "%d اقتباس بلا رقم صفحة" % len(bad_page) + ((": " + "؛ ".join(bad_page[:3])) if bad_page else ""), "G14:1339")
    rep.add("ERROR" if too_long else "OK", "الاقتباسات", "%d اقتباس ≥ %d كلمة (H5)" % (len(too_long), LIMITS["quote_words"]), "H5 [قاعدة الأداة]")


def check_refs(text, rep):
    secs = sections(text)
    ref = next((s for s in secs if norm(s[1]).strip(" .0123456789") in ("المراجع", "قائمة المراجع")), None)
    t = text if not ref else text.replace(ref[2], "")
    cites = set()
    for m in CIT.finditer(t):
        cites.add((norm(m.group(1)).split()[0] if m.group(1).split() else "", m.group(2)))
    for m in NARR.finditer(t):
        cites.add((norm(m.group(1)).split()[0], m.group(2)))
    if not ref:
        if cites:
            rep.add("ERROR", "المراجع", "استشهادات في المتن (%d) ولا قائمة مراجع" % len(cites), "G14:1361")
        return
    entries = []
    for ln in ref[2].split("\n"):
        ln = re.sub(r"^\s*[-*\d.]+\s*", "", ln).strip()
        if not ln or ln.startswith("[") or PLACE.search(ln):
            continue
        ym = re.search(r"\(\s*((?:19|20)\d{2}|د\.ت\.?)[a-z]?\s*\)", ln)
        sur = norm(re.split(r"[،,]", ln)[0]).strip()
        entries.append((sur.split()[0] if sur.split() else "", ym.group(1) if ym else ""))
    refset = set(entries)
    no_ref = sorted(c for c in cites if c not in refset)
    unused = sorted(e for e in refset if e not in cites)
    rep.add("ERROR" if no_ref else "OK", "المراجع", "استشهادات بلا مرجع في القائمة (%d)%s" % (len(no_ref), (": " + "؛ ".join("%s %s" % c for c in no_ref[:5])) if no_ref else ""), "G14:1361")
    rep.add("WARN" if unused else "OK", "المراجع", "مراجع غير مستشهد بها في المتن (%d)%s [مطابقة تقريبية]" % (len(unused), (": " + "؛ ".join("%s %s" % c for c in unused[:5])) if unused else ""), "G15:1600")


def registry_numbers(path):
    """كل الأرقام الواردة في data_registry.json (أي عمق) كنصوص موحّدة."""
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    out = set()
    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        else:
            for m in re.finditer(r"\d+(?:[.,٫]\d+)?", str(x).translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))):
                out.add(m.group(0).replace(",", ".").replace("٫", "."))
    walk(data)
    return out


def check_numbers(text, registry_path, rep):
    """H2/M3: أرقام النص غير المسجَّلة في data_registry. تقريبي: الأعداد الصحيحة < 10 والسنوات 1900–2099
    وترقيم العناوين والبنود والجداول والاستشهادات وقيم الدلالة المعيارية تُستثنى."""
    try:
        reg = registry_numbers(registry_path)
    except (OSError, json.JSONDecodeError) as e:
        rep.add("ERROR", "الأرقام (H2)", "تعذّر قراءة data_registry: %s" % e, "H2"); return
    t = re.sub(r"^```.*?^```", "", text, flags=re.S | re.M)
    t = PLACE.sub(" ", t)
    t = re.sub(r"^\s*#{1,6}.*$", "", t, flags=re.M)                       # العناوين
    t = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", t, flags=re.M)             # ترقيم البنود
    t = re.sub(r"(?:جدول|الشكل|شكل)\s*\(\s*\d+\s*\)", " ", t)           # ترقيم الجداول/الأشكال
    t = CIT.sub(" ", t); t = NARR.sub(" ", t)
    t = re.sub(r"\(\s*ص\s*[\d\-–]+\s*\)", " ", t)
    t = t.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    std = {"0.05", "0.01", "0.001", "0.10", "0.1"}
    unknown = []
    for m in re.finditer(r"(?<![\w.])\d+(?:[.,٫]\d+)?%?", t):
        raw = m.group(0).rstrip("%")
        n = raw.replace(",", ".")
        if n in reg or n in std:
            continue
        if re.fullmatch(r"(?:19|20)\d{2}", n):
            continue
        if re.fullmatch(r"\d", n):
            continue
        unknown.append(m.group(0))
    unknown_u = sorted(set(unknown))
    rep.add("ERROR" if unknown_u else "OK", "الأرقام (H2/M3)",
            "%d رقماً في النص بلا إدخال في data_registry%s [فحص تقريبي]" % (len(unknown_u), (": " + "، ".join(unknown_u[:8])) if unknown_u else ""), "H2")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--kind", choices=["thesis", "plan", "abstract"], default="thesis")
    ap.add_argument("--title")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--registry", help="passport/data_registry.json لفحص H2: أرقام النص مقابل ما قدمه الباحث")
    a = ap.parse_args()
    try:
        text = pathlib.Path(a.file).read_text(encoding="utf-8")
    except FileNotFoundError:
        print("خطأ: ملف غير موجود", a.file, file=sys.stderr); return 2
    rep = Rep()
    check_title(text, a.title, rep)
    if a.kind == "plan":
        check_plan(text, rep)
        check_quotes(text, rep); check_refs(text, rep)
    elif a.kind == "abstract":
        check_abstract(text, rep)
    else:
        check_chapters(text, rep); check_abstract(text, rep); check_tables_figures(text, rep)
        check_quotes(text, rep); check_refs(text, rep)
    if a.registry:
        check_numbers(text, a.registry, rep)
    ph = len(PLACE.findall(text))
    rep.add("INFO", "فراغات", "%d فراغاً موسوماً ما زال مفتوحاً" % ph, "H2/H1")
    err = sum(1 for i in rep.items if i["level"] == "ERROR")
    out = {"status": "FAIL" if err else "PASS", "errors": err, "items": rep.items,
           "note": "فحص تقريبي للنص المكتوب؛ الخطوط والهوامش والتباعد وترقيم الصفحات تُراجع يدوياً في Word (G03:158–165)."}
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print("الحالة:", out["status"], "(أخطاء: %d)" % err)
        for i in rep.items:
            print({"OK": "✔", "ERROR": "✘", "WARN": "!", "INFO": "·"}[i["level"]], i["check"], "—", i["msg"], ("[%s]" % i["ref"]) if i["ref"] else "")
        print(out["note"])
    return 1 if err else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:  # مثل `| head`
        sys.exit(0)

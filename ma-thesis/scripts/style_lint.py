#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""style_lint.py — فحص أسلوب النص العربي الأكاديمي (طبقة 5 من anti_ai_style.md).

الأوضاع:
  style_lint.py FILE [--rules style_rules.json] [--profile style_profile.json] [--json]
  style_lint.py --calibrate FILE [--out profile.json]
  style_lint.py --compare ORIGINAL REVISED [--rules ...] [--json]

الحالة: يخرج بالرمز 1 عند أي تنبيه أحمر، 0 غير ذلك، 2 عند خطأ في المدخلات.
تنبيه صريح: المقاييس **تقريبية** ولا تضمن اجتياز أي كاشف للذكاء الاصطناعي.
أرقام الأنماط 1–26 وفئاتها (أ–و) وأوزانها (قوي / ضعيف وحده) من humanizer 3.1.0
(references/humanizer_upstream/SKILL.upstream.md)، والتكييف العربي في references/humanizer_patterns_ar.md.
"""
import argparse, collections, json, pathlib, re, statistics, sys

HERE = pathlib.Path(__file__).resolve().parent
AR = r"\u0621-\u064A"
DIAC = set(chr(c) for c in list(range(0x064B, 0x0653)) + [0x0670, 0x0640])
FOLD = {"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي"}
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


# ------------------------------------------------------------------ تطبيع
def norm_map(text):
    """يعيد (النص الموحَّد، خريطة موضع_موحَّد→موضع_أصلي). يزيل التشكيل والتطويل ويوحّد الهمزات."""
    out, idx = [], []
    for i, ch in enumerate(text):
        if ch in DIAC:
            continue
        out.append(FOLD.get(ch, ch))
        idx.append(i)
    return "".join(out), idx


def norm(text):
    return norm_map(text)[0]


def snippet(orig, idx, s, e, pad=25):
    a = idx[s] if s < len(idx) else 0
    b = idx[min(e - 1, len(idx) - 1)] + 1 if idx else 0
    t = orig[max(0, a - pad): b + pad].replace("\n", " ")
    return t.strip()


def phrase_re(p):
    p = norm(p).strip()
    p = re.sub(r"\s+[بلك]$", "", p)  # «بـ» الملتصقة بما بعدها
    body = r"\s+".join(re.escape(w) for w in p.split())
    return re.compile(r"(?<![" + AR + r"])[وف]?" + body + r"(?![" + AR + r"])")


def rx(p):
    return re.compile(norm(p), re.S)


def words(t):
    return re.findall(r"[" + AR + r"0-9A-Za-z]+", t)


# ------------------------------------------------------------------ تحليل البنية
class Block:
    def __init__(self, kind, text, line, section, level=0):
        self.kind, self.text, self.line, self.section, self.level = kind, text, line, section, level


def parse_blocks(text):
    blocks, cur, cur_line, section, fence = [], [], 0, "", False
    cur_head_level = 0
    def flush():
        nonlocal cur
        if cur:
            blocks.append(Block("para", " ".join(s.strip() for s in cur), cur_line, section))
            cur = []
    for n, line in enumerate(text.split("\n"), 1):
        s = line.strip()
        if s.startswith("```"):
            flush(); fence = not fence; continue
        if fence:
            continue
        if not s:
            flush(); continue
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            flush()
            section = m.group(2).strip()
            blocks.append(Block("heading", section, n, section, len(m.group(1))))
            continue
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", s):
            flush(); blocks.append(Block("hr", s, n, section)); continue
        if s.startswith("|"):
            flush(); blocks.append(Block("table", s, n, section)); continue
        if s.startswith(">"):
            flush(); blocks.append(Block("quote", s.lstrip("> ").strip(), n, section)); continue
        if re.match(r"^([-*+]|\d+[.)])\s+", s):
            flush(); blocks.append(Block("list", re.sub(r"^([-*+]|\d+[.)])\s+", "", s), n, section)); continue
        if not cur:
            cur_line = n
        cur.append(s)
    flush()
    return blocks


def mask(text, regexes):
    for r in regexes:
        text = re.sub(r, lambda m: " " * len(m.group(0)), text)
    return text


def sentences(ntext):
    return [(m.start(), m.end(), m.group(0).strip()) for m in
            re.finditer(r".+?(?:[.؟!?]+(?=\s|$)|$)", ntext, re.S) if m.group(0).strip()]


def skip_section(sec):
    n = norm(sec)
    return any(k in n for k in ("المراجع", "الملاحق", "references"))


# ------------------------------------------------------------------ الفحص
def lint(text, rules, profile=None):
    th = rules["thresholds"]
    flags, info = [], collections.Counter()
    pc = rules["protected_scope"]
    ph_re = re.compile(pc["placeholder_regex"])
    q_re = re.compile(pc["quote_regex"])
    cit_re = re.compile(rules["vague_claims"]["citation_regex"])

    blocks = parse_blocks(text)
    pats = {p["id"]: p for p in rules["patterns"]}
    compiled = {}
    for p in rules["patterns"]:
        if p.get("disabled"):
            continue
        items = []
        for ph in p.get("phrases", []):
            lvl = None
            if isinstance(ph, dict):
                ph, lvl = ph["p"], ph["level"]
            items.append((phrase_re(ph), lvl, ph))
        for r in p.get("regex", []):
            items.append((rx(r), None, r))
        compiled[p["id"]] = items
    ban = rules["banned"]
    ban_c = {}
    for k, v in ban.items():
        if k.startswith("_"):
            continue
        ban_c[k] = [(phrase_re(x), x) for x in v.get("phrases", [])] + [(rx(x), x) for x in v.get("regex", [])]
    pron = [(rx(r), r) for r in rules["person_pronouns"]["regex"]]
    conn = [phrase_re(x) for x in rules["connectors"]["phrases"]]

    def add(rule, pid, level, para, snip, note=""):
        p = pats.get(pid, {})
        flags.append({"rule": rule, "pattern": pid, "group": p.get("group", ""), "weight": p.get("weight", ""),
                      "level": level, "line": para.line, "section": para.section, "snippet": snip[:110], "note": note})

    all_prose_words, all_sent_lens, all_openers = 0, [], []
    weak_by_para = collections.defaultdict(set)
    density = collections.Counter()
    conn_total = 0
    conn_start = 0
    n_sent_total = 0
    placeholders = 0
    triad_hits = 0
    dash_total = 0
    bold_spans, bold_list = 0, 0
    quote_styles = collections.Counter()
    emoji_re = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2190-\u21FF\u2B00-\u2BFF]")
    hr_count = sum(1 for b in blocks if b.kind == "hr")
    prev_para = None
    last_heading = None
    punct = collections.Counter()

    for bi, b in enumerate(blocks):
        if b.kind == "heading":
            last_heading = b
            if emoji_re.search(b.text):
                add("رمز تعبيري/سهم في عنوان", 20, "yellow", b, b.text)
            continue
        if b.kind in ("table", "hr", "quote"):
            continue
        if skip_section(b.section):
            continue
        raw = b.text
        placeholders += len(ph_re.findall(norm(raw)))
        # تغميق
        spans = re.findall(r"\*\*[^*]+\*\*", raw)
        if b.kind == "list" and re.match(r"^\*\*[^*]+\*\*\s*[:：]", raw):
            bold_list += 1
        if b.kind == "para":
            bold_spans += len(spans)
        for m in re.finditer(r"«|»|“|”|\"", raw):
            quote_styles[m.group(0)] += 1
        if emoji_re.search(raw):
            add("رمز تعبيري/سهم في النص", 20, "yellow", b, emoji_re.search(raw).group(0))
        masked = mask(raw, [q_re.pattern, ph_re.pattern])
        nm, idx = norm_map(masked)
        nm_nocite = mask(nm, [cit_re.pattern])  # للأنماط التي يربكها التوثيق
        # الضمائر (G03:182)
        for r, src in pron:
            for m in r.finditer(nm_nocite):
                add("ضمير متكلم/مخاطب (G03:182)", 0, rules["person_pronouns"]["level"], b, snippet(masked, idx, m.start(), m.end()))
        # العبارات الممنوعة (طبقة 2)
        sents = sentences(nm)
        last_s = sents[-1] if sents else None
        for k, lst in ban_c.items():
            lvl = ban[k]["level"]
            for r, src in lst:
                for m in r.finditer(nm_nocite):
                    if k == "transitions":
                        continue
                    if ban[k].get("scope") == "paragraph_last" and not (last_s and m.start() >= last_s[0]):
                        continue
                    add("عبارة ممنوعة: " + k, 0, lvl, b, snippet(masked, idx, m.start(), m.end()))
        # الأنماط المعتمدة على العبارات
        in_tamheed = "تمهيد" in norm(b.section)
        para_distinct = collections.defaultdict(set)
        for pid, items in compiled.items():
            p = pats[pid]
            if p.get("special"):
                continue
            if p.get("skip_under_heading") and in_tamheed:
                continue
            for r, lvl, src in items:
                for m in r.finditer(nm_nocite if pid != 17 else nm):
                    if p.get("scope") == "paragraph_last" and not (last_s and m.start() >= last_s[0]):
                        continue
                    sn = snippet(masked, idx, m.start(), m.end())
                    if pid == 17 and p.get("requires_citation"):
                        si = next((i for i, s in enumerate(sents) if s[0] <= m.start() < s[1] or s[0] <= m.start() <= s[1]), None)
                        near = " ".join(s[2] for s in sents[si: si + 2]) if si is not None else nm
                        if cit_re.search(near):
                            continue
                    if p.get("cluster_min"):
                        para_distinct[pid].add(src)
                        continue
                    if p.get("density_yellow_per_100w") is not None or p.get("per_hit_level") == "info":
                        density[pid] += 1
                        if pid == 6:
                            triad_hits += 1
                        continue
                    level = lvl or p["level"]
                    if p["weight"] == "weak":
                        weak_by_para[b.line].add(pid)
                        density[pid] += 1
                        continue
                    add(p["name_ar"], pid, level, b, sn)
        for pid, srcs in para_distinct.items():
            p = pats[pid]
            if len(srcs) >= p["cluster_min"]:
                add(p["name_ar"] + " (تجمّع)", pid, p.get("cluster_level", "yellow"), b, "، ".join(sorted(srcs))[:100])
        # الإيقاع: للفقرات النثرية فقط
        if b.kind != "para":
            continue
        wl = words(nm)
        all_prose_words += len(wl)
        punct["comma"] += raw.count("،") + raw.count(",")
        punct["semi"] += raw.count("؛")
        punct["paren"] += raw.count("(")
        # شرطات
        dashes = len(re.findall(r"(?<!\d)\s[—–-]{1,2}\s|—|(?<!\d)–(?!\d)", nm_nocite))
        dash_total += dashes
        if dashes >= 2:
            weak_by_para[b.line].add(8)
        if len(quote_styles) > 1:
            weak_by_para[b.line].add(21)
        ssl = [len(words(s[2])) for s in sents]
        n_sent_total += len(sents)
        all_sent_lens += ssl
        for s, l in zip(sents, ssl):
            if l >= th["long_sentence_words_red"]:
                add("جملة طويلة جداً (%d كلمة)" % l, 0, "red", b, s[2][:90])
            elif l >= th["long_sentence_words_yellow"]:
                add("جملة طويلة (%d كلمة)" % l, 0, "yellow", b, s[2][:90])
        # تباين الأطوال داخل الفقرة
        if len(ssl) >= th["paragraph_cv_min_sentences"]:
            mu = statistics.mean(ssl)
            cv = statistics.pstdev(ssl) / mu if mu else 0
            if cv < th["paragraph_cv_red_below"]:
                add("أطوال جمل متقاربة جداً (CV=%.2f)" % cv, 7, "red", b, "فقرة من %d جمل" % len(ssl), "نمط الإيقاع بالقاعدة")
            elif cv < th["paragraph_cv_yellow_below"]:
                add("أطوال جمل متقاربة (CV=%.2f)" % cv, 7, "yellow", b, "فقرة من %d جمل" % len(ssl))
        # صف من الجمل المبتورة
        run = 0
        for l in ssl + [99]:
            if l <= th["fragment_run_max_words"]:
                run += 1
            else:
                if run >= th["fragment_run_min_len"]:
                    add("صف جمل مبتورة", 2, "yellow", b, "%d جمل ≤%d كلمات" % (run, th["fragment_run_max_words"]))
                run = 0
        # بدايات الجمل
        ops = []
        for s in sents:
            w = words(s[2])
            if not w:
                continue
            f = w[0]
            if len(f) >= 4 and f[0] in "وف":
                f = f[1:]
            ops.append(f)
            if any(c.match(nm, s[0] + (len(nm[s[0]:]) - len(nm[s[0]:].lstrip()))) for c in conn):
                conn_start += 1
        all_openers += ops
        runl = 1
        for i in range(1, len(ops) + 1):
            if i < len(ops) and ops[i] == ops[i - 1]:
                runl += 1
            else:
                if runl >= th["opener_repeat_red_consecutive"]:
                    add("بداية جمل متكررة: «%s» ×%d" % (ops[i - 1], runl), 7, "red", b, ops[i - 1])
                runl = 1
        for c in conn:
            conn_total += len(c.findall(nm_nocite))
        # وصف الوثيقة: استثناء تحت «تمهيد»
        # عنوان مكرر في أول جملة (24)
        if last_heading is not None and bi > 0 and blocks[bi - 1] is last_heading and sents:
            ht = set(words(norm(re.sub(r"^[\d.\s]+", "", last_heading.text))))
            st = words(sents[0][2])
            if ht and len(sents) > 1 and len(st) <= th["heading_repeat_max_words"]:
                ov = len(ht & set(st)) / len(ht)
                if ov >= th["heading_repeat_overlap"]:
                    add("عنوان مكرر في أول جملة", 24, "yellow", b, sents[0][2][:80])
        # فقرة من سطر واحد تتلو فقرة طويلة (نمط 2: معلومة فقط)
        if len(sents) == 1 and len(wl) <= 10 and prev_para is not None and prev_para > 40:
            add("فقرة من سطر واحد بعد فقرة طويلة", 2, "info", b, sents[0][2][:80], "راجع: هل تضيف معلومة؟")
        prev_para = len(wl)

    # ---- تجميع على مستوى النص
    nW = max(all_prose_words, 1)
    metrics = {"prose_words": all_prose_words, "sentences": n_sent_total, "placeholders": placeholders}
    if all_prose_words >= th["min_words_for_cv"] and all_sent_lens:
        mu = statistics.mean(all_sent_lens)
        cv = statistics.pstdev(all_sent_lens) / mu if mu else 0
        metrics.update({"mean_sentence_len": round(mu, 1), "sentence_len_cv": round(cv, 3)})
        if cv < th["overall_cv_yellow_below"]:
            flags.append({"rule": "تباين أطوال الجمل منخفض في النص كله (CV=%.2f)" % cv, "pattern": 7, "group": "ب", "weight": "strong", "level": "yellow", "line": 0, "section": "", "snippet": "", "note": ""})
    if len(all_openers) >= th["opener_top_share_min_sentences"]:
        top, cnt = collections.Counter(all_openers).most_common(1)[0]
        share = cnt / len(all_openers)
        metrics["top_opener"] = {"word": top, "share": round(share, 2)}
        if share >= th["opener_top_share_yellow"]:
            flags.append({"rule": "كلمة افتتاح واحدة تتكرر في %.0f%% من الجمل: «%s»" % (share * 100, top), "pattern": 7, "group": "ب", "weight": "strong", "level": "yellow", "line": 0, "section": "", "snippet": "", "note": ""})
    cstart_share = conn_start / n_sent_total if n_sent_total else 0
    metrics["connector_start_share"] = round(cstart_share, 2)
    metrics["connectors_per_100w"] = round(conn_total * 100 / nW, 2)
    for lvl, key_s, key_d in (("red", "connector_start_share_red", "connector_per_100w_red"), ("yellow", "connector_start_share_yellow", "connector_per_100w_yellow")):
        if cstart_share >= th[key_s] or conn_total * 100 / nW >= th[key_d]:
            flags.append({"rule": "كثافة روابط الانتقال عالية (حصة البدايات %.0f%%، %.1f لكل 100 كلمة)" % (cstart_share * 100, conn_total * 100 / nW), "pattern": 0, "group": "", "weight": "", "level": lvl, "line": 0, "section": "", "snippet": "", "note": "طبقة 2/5: قوالب انتقال آلية"})
            break
    metrics["dashes_per_100w"] = round(dash_total * 100 / nW, 2)
    if True:
        d = density[6] * 100 / nW
        metrics["triads_per_100w"] = round(d, 2)
        if d >= th["triad_per_100w_red"]:
            flags.append({"rule": "ثلاثيات متتابعة بكثافة (%.1f/100 كلمة)" % d, "pattern": 6, "group": "ب", "weight": "strong", "level": "red", "line": 0, "section": "", "snippet": "", "note": ""})
        elif d >= th["triad_per_100w_yellow"]:
            flags.append({"rule": "ثلاثيات متتابعة بكثافة (%.1f/100 كلمة)" % d, "pattern": 6, "group": "ب", "weight": "strong", "level": "yellow", "line": 0, "section": "", "snippet": "", "note": "التقييم النهائي بشري"})
    for pid in (15, 18):
        p = pats[pid]
        d = density[pid] * 100 / nW
        metrics["p%d_per_100w" % pid] = round(d, 2)
        if d >= p["density_yellow_per_100w"]:
            flags.append({"rule": p["name_ar"] + " (كثافة %.1f/100 كلمة)" % d, "pattern": pid, "group": p["group"], "weight": p["weight"], "level": "yellow", "line": 0, "section": "", "snippet": "", "note": ""})
    # تغميق
    bd = bold_spans * 100 / nW
    metrics["bold_spans_per_100w"] = round(bd, 2)
    if bd >= th["bold_spans_per_100w_yellow"] or bold_list >= 3:
        flags.append({"rule": "تغميق للزينة (%d نطاقاً، %d بنداً بعنوان مغمّق)" % (bold_spans, bold_list), "pattern": 19, "group": "د", "weight": "strong", "level": "yellow", "line": 0, "section": "", "snippet": "", "note": ""})
    if hr_count >= 2:
        flags.append({"rule": "فواصل أفقية بين الأقسام (%d)" % hr_count, "pattern": 20, "group": "د", "weight": "strong", "level": "yellow", "line": 0, "section": "", "snippet": "", "note": ""})
    # اتساق التنصيص (بديل 21)
    styles = {"«»": quote_styles["«"] + quote_styles["»"], "“”": quote_styles["“"] + quote_styles["”"], '""': quote_styles['"']}
    used = [k for k, v in styles.items() if v]
    metrics["quote_styles"] = used
    # تجمّع الأنماط الضعيفة
    for line, ids in weak_by_para.items():
        if len(ids) >= th["weak_cluster_red_min_patterns"]:
            flags.append({"rule": "تجمّع أنماط ضعيفة {%s} في مقطع واحد" % "، ".join(str(i) for i in sorted(ids)), "pattern": min(ids), "group": "ب", "weight": "weak", "level": "red", "line": line, "section": "", "snippet": "", "note": "الأنماط الضعيفة وحدها لا تُعدّ حمراء إلا مجتمعة"})
    # انجراف الأسلوب
    if profile and "mean_sentence_len" in metrics:
        d = []
        if abs(metrics["mean_sentence_len"] - profile["mean_sentence_len"]) / max(profile["mean_sentence_len"], 1) > th["drift_mean_len_rel"]:
            d.append("متوسط طول الجملة")
        if abs(metrics["sentence_len_cv"] - profile["sentence_len_cv"]) > th["drift_cv_abs"]:
            d.append("تباين الأطوال")
        if abs(metrics["connector_start_share"] - profile["connector_start_share"]) > th["drift_connector_share_abs"]:
            d.append("حصة الروابط في البدايات")
        if d:
            flags.append({"rule": "انجراف عن ملف الباحث: " + "، ".join(d), "pattern": 0, "group": "", "weight": "", "level": "yellow", "line": 0, "section": "", "snippet": "", "note": "style_profile"})
    merged, seen = [], {}
    for f in flags:
        k = (f["rule"], f["pattern"], f["line"], f["level"])
        if k in seen:
            seen[k]["count"] = seen[k].get("count", 1) + 1
            continue
        f["count"] = 1
        seen[k] = f
        merged.append(f)
    flags = merged
    red = sum(1 for f in flags if f["level"] == "red")
    yellow = sum(1 for f in flags if f["level"] == "yellow")
    return {"status": "FAIL" if red else ("WARN" if yellow else "PASS"), "red": red, "yellow": yellow,
            "metrics": metrics, "flags": flags,
            "disclaimer": "مقاييس تقريبية؛ لا تضمن اجتياز كاشفات الذكاء الاصطناعي."}


def profile_of(text, rules):
    r = lint(text, rules)
    m = r["metrics"]
    if "mean_sentence_len" not in m:
        raise SystemExit("العينة أقصر من اللازم (أقل من %d كلمة نثرية)" % rules["thresholds"]["min_words_for_cv"])
    nW = max(m["prose_words"], 1)
    commas = len(re.findall(r"[،,]", text)); semi = text.count("؛"); par = text.count("(")
    return {"mean_sentence_len": m["mean_sentence_len"], "sentence_len_cv": m["sentence_len_cv"],
            "connector_start_share": m["connector_start_share"], "connectors_per_100w": m["connectors_per_100w"],
            "dashes_per_100w": m["dashes_per_100w"], "commas_per_100w": round(commas * 100 / nW, 2),
            "semicolons_per_100w": round(semi * 100 / nW, 2), "parens_per_100w": round(par * 100 / nW, 2),
            "sample_words": m["prose_words"]}


# ------------------------------------------------------------------ مقارنة النطاق المحمي
def compare(orig, rev, rules):
    pc = rules["protected_scope"]
    ph = re.compile(pc["placeholder_regex"]); cit = re.compile(pc["citation_regex"])
    num = re.compile(pc["number_regex"]); quo = re.compile(pc["quote_regex"])
    issues = []

    def ms(rx_, t, normalise=True):
        t = norm(t) if normalise else t
        return collections.Counter(re.sub(r"\s+", " ", m.group(0)).translate(ARABIC_DIGITS) for m in rx_.finditer(t))

    def diff(name, a, b, level="red", added_level="red"):
        for k, c in (a - b).items():
            issues.append({"check": name, "level": level, "kind": "مفقود/متغيّر", "item": k, "count": c})
        for k, c in (b - a).items():
            issues.append({"check": name, "level": added_level, "kind": "مضاف", "item": k, "count": c})

    diff("فراغات موسومة", ms(ph, orig), ms(ph, rev), "red", "info")
    # الأرقام: بعد إزالة الفراغات الموسومة والاقتباسات من الحساب المنفصل؟ تُحسب في النص كله.
    diff("أرقام", ms(num, orig), ms(num, rev))
    diff("استشهادات (مؤلف، سنة، صفحة)", ms(cit, orig), ms(cit, rev))
    diff("اقتباسات حرفية", ms(quo, orig, False), ms(quo, rev, False))
    ho = [b.text for b in parse_blocks(orig) if b.kind == "heading"]
    hr = [b.text for b in parse_blocks(rev) if b.kind == "heading"]
    if ho != hr:
        issues.append({"check": "العناوين والترقيم", "level": "red", "kind": "اختلاف", "item": "تسلسل العناوين لم يبق مطابقاً", "count": 1})
    # الأقسام المحمية: صياغة الأهداف/الأسئلة/الفرضيات... كما هي (H9)
    def prot(text):
        out = collections.defaultdict(list)
        for b in parse_blocks(text):
            if b.kind in ("list", "para", "quote") and any(k in norm(b.section) for k in pc["protected_section_heading_keywords"]):
                out[norm(b.section)].append(re.sub(r"\s+", " ", norm(b.text)).strip())
        return out
    po, pr = prot(orig), prot(rev)
    for sec, lines in po.items():
        if pr.get(sec) != lines:
            issues.append({"check": "قسم محمي (H9 دون تغيير)", "level": "red", "kind": "اختلاف", "item": sec, "count": 1})
    red = sum(1 for i in issues if i["level"] == "red")
    return {"status": "FAIL" if red else "PASS", "red": red, "issues": issues}


# ------------------------------------------------------------------ مخرجات
def print_lint(r):
    print("الحالة: %s  (أحمر %d، أصفر %d)" % (r["status"], r["red"], r["yellow"]))
    print("المقاييس:", json.dumps(r["metrics"], ensure_ascii=False))
    order = {"red": 0, "yellow": 1, "info": 2}
    for f in sorted(r["flags"], key=lambda f: (order[f["level"]], f["line"])):
        tag = {"red": "🔴", "yellow": "🟡", "info": "·"}[f["level"]]
        pid = ("نمط %d/%s/%s" % (f["pattern"], f["group"], "ضعيف" if f["weight"] == "weak" else "قوي")) if f["pattern"] else "قاعدة الأداة"
        cnt = (" ×%d" % f["count"]) if f.get("count", 1) > 1 else ""
        print("%s س%s [%s] %s%s — %s" % (tag, f["line"], pid, f["rule"], cnt, f["snippet"]))
    print(r["disclaimer"])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?")
    ap.add_argument("--rules", default=str(HERE / "style_rules.json"))
    ap.add_argument("--profile")
    ap.add_argument("--calibrate")
    ap.add_argument("--out")
    ap.add_argument("--compare", nargs=2, metavar=("ORIGINAL", "REVISED"))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        rules = json.loads(pathlib.Path(a.rules).read_text(encoding="utf-8"))
        if a.calibrate:
            prof = profile_of(pathlib.Path(a.calibrate).read_text(encoding="utf-8"), rules)
            s = json.dumps(prof, ensure_ascii=False, indent=1)
            if a.out:
                pathlib.Path(a.out).write_text(s, encoding="utf-8")
            print(s); return 0
        if a.compare:
            o, v = (pathlib.Path(p).read_text(encoding="utf-8") for p in a.compare)
            r = compare(o, v, rules)
            if a.json:
                print(json.dumps(r, ensure_ascii=False, indent=1))
            else:
                print("مقارنة النطاق المحمي:", r["status"])
                for i in r["issues"]:
                    print(" ", {"red": "🔴", "info": "·"}.get(i["level"], "🟡"), i["check"], "—", i["kind"], "—", i["item"], "×%d" % i["count"])
            return 1 if r["red"] else 0
        if not a.file:
            ap.error("مطلوب ملف النص")
        prof = json.loads(pathlib.Path(a.profile).read_text(encoding="utf-8")) if a.profile else None
        r = lint(pathlib.Path(a.file).read_text(encoding="utf-8"), rules, prof)
        print(json.dumps(r, ensure_ascii=False, indent=1)) if a.json else print_lint(r)
        return 1 if r["red"] else 0
    except FileNotFoundError as e:
        print("خطأ: ملف غير موجود:", e.filename, file=sys.stderr); return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:  # مثل `| head`
        sys.exit(0)

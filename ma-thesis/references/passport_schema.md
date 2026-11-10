# «الجواز»: بنيته وقواعده

**الغاية:** اقتصاد التوكن. لا تُعاد قراءة المحادثة ولا الفصول؛ يُحمَّل `index.json` وحده دائماً، وتُقرأ الشظايا **بالمفتاح فقط** عبر `scripts/passport.py`. النصوص الطويلة في `drafts/`.

يُنشأ في **مجلد عمل الباحث** (`passport/`) لا داخل مجلد الـ skill.

```
passport/
  index.json          ← يُحمَّل دائماً (صغير)
  sources.json  lit_cards.json  claims.json  decisions.json  style_profile.json
  learned_rules.json  corrections_log.json  data_registry.json  audit_log.json
  drafts/<اسم>.v<N>.md
```

## index.json

```json
{"schema":1,"title":"…","study_type":"quantitative|qualitative|mixed|theoretical","discipline":"…",
 "stage":"S0|S1|S2|S3|S4|S5|G-A|S6|S7|S8|G-B|S9",
 "fragments":{"sources":{"sha256":"…","version":3,"bytes":1234,"updated":"…"}, "…":{}},
 "drafts":[{"name":"intro","version":2,"file":"drafts/intro.v2.md","sha256":"…","saved":"…","note":""}],
 "gates":{"G-A":"passed|failed|skipped:سبب","G-B":"…"},"notes":{},"created":"…","updated":"…"}
```

## الشظايا (JSON)

| الشظية | النوع | مفتاح الإدخال | الحقول الأساسية |
|---|---|---|---|
| `sources` | كائن | `S01…` | `status` ∈ {verified, partial, needs_user_text, unverifiable, rejected, candidate}؛ `title`, `authors[]`, `year`, `venue`/`publisher`, `doi`, `pdf_url`, `access` (open/restricted), `type` (journal/book/thesis/conference/report/web), `publisher_class` (university/research_center/official/international/other), `evidence_pages{goal,method,sample,instrument,results,conclusion}`, `checks{V1..V6}`, `reason` (لغير verified), `alternatives[]` |
| `lit_cards` | كائن | `L01…` | `source_id`, `relevance` (main/supporting/excluded), وكل حقل من `goal, method, sample, instrument, results` بصيغة `{text, page}` (إعادة صياغة لا نقل)، `title_ar_review` للعناوين الأجنبية («تحتاج مراجعة») |
| `claims` | كائن | `C001…` | `status:"rejected"` + `reason` لادعاء فُحص ولم يطابق مصدره (يُسجَّل ولا يدخل النص ولا يُفحص بـH1)؛ `kind` ∈ {cited, own, data}؛ `cited`: `source_ids[]` و`page` و`section` و`quote` (bool)؛ `data`: `data_ref` ← مفتاح في `data_registry` |
| `decisions` | قائمة | — | `{t, stage, decision, by:"user"}`: موافقات البوابات، استثناءات H7/الكلاسيكي، قرارات الباحث المنهجية |
| `style_profile` | كائن | — | مخرج `style_lint --calibrate` + `notes` + `approved_by_user` |
| `learned_rules` | كائن | `R01…` | `rule`, `scope`, `evidence` (مفاتيح من corrections_log), **`approved_by_user:true`** |
| `corrections_log` | قائمة | — | `{t, kind:"language|method|citation", before, after, rule, accepted}` |
| `data_registry` | كائن | `D01…` | **ما قدمه الباحث فقط (H2):** `{label, value|file, provided_on, source_file, note}`. ملخصات مجمَّعة لا بيانات مستجيبين؛ لا بريد ولا هاتف ولا أسماء |
| `audit_log` | قائمة | — | سجل تلقائي لكل كتابة: `{t, action, detail}`؛ **لا يُحذف منه** |

## الأوامر (`python3 scripts/passport.py --dir passport …`)

`init · show · meta · read · write · del · append · draft save|list|get · validate · rehash --confirm · pack · unpack`

- **كتابة ذرّية** (ملف مؤقت + `os.replace`) وقفل بملف؛ **sha256 لكل شظية ومسودة** في الفهرس.
- `--expect-version N` يرفض الكتابة بخروج 3 إن تغيّر الإصدار (تعارض).
- `validate` يفشل (خروج 1) في: هاش لا يطابق (تعديل يدوي)، JSON تالف، مخطط غير مدعوم، مفتاح محظور (`password/secret/token/api_key`)، بريد إلكتروني في data_registry/decisions/claims، **ادعاء `cited` إلى مصدر غير `verified`** (H1)، ادعاء بلا صفحة، **ادعاء `data` بلا إدخال في data_registry** (H2)، قاعدة متعلَّمة بلا موافقة، بطاقة بمصدر غير موجود، `verified` بلا (title, authors, year, pdf_url, evidence_pages).
- **مرشّح سياسة المصدر (H7) آلي:** `write sources` و`validate` يرفضان `verified` لمصدر نطاقه ويكيبيديا/مدونات/منصات تواصل/مواقع تعليمية عامة، أو رسالة `thesis_level=diploma`، أو `type=web` بناشر `publisher_class` ليس جامعة/مركز أبحاث/جهة رسمية/دولية. القائمة في `scripts/passport.py` (BLOCKED_HOSTS) **[اجتهاد]** وهي مرشّح أولي فقط؛ الحكم النهائي للمتحقق (V6).
- `pack` يتحقق أولاً ثم يضغط (index + شظايا + مسودات فقط)؛ `unpack` يرفض أي اسم خارج القائمة المسموحة أو يحوي `..` أو مساراً مطلقاً (**حماية zip-slip**) ثم يعيد `validate`.
- عند جواز تالف أو بإصدار آخر: `validate` يفشل، تُعرض الأجزاء السليمة، **ولا تُصلَح الشظايا يدوياً دون تأكيد الباحث**؛ `rehash --confirm` لقبول تعديل يدوي واعٍ ويُسجَّل.

## التعلم المستمر

لا يتغير النموذج؛ **يتعلم الجواز**. بعد تصحيحات متكررة من النوع نفسه (مثلاً: حذف «علاوة على ذلك» ثلاث مرات) تقترح الأداة قاعدة وتعرضها **كما ستُحفظ حرفياً**:

```
[مقترح قاعدة R03] النطاق: كل الأقسام — النص: «يُحذف "علاوة على ذلك" في بداية الجملة» — الأدلة: corrections_log #12,#15,#19
هل تعتمدها؟ (نعم / لا / عدّل)
```

لا تُحفظ في `learned_rules` قبل «نعم»، ويُسجَّل القرار في `decisions` والتصحيحات في `corrections_log`. وتُقرأ القواعد المعتمدة وحدها عند الكتابة اللاحقة، **ولا تتقدم على H1–H12 أو الدليل**.

## التخزين والتسليم

لا وصول مباشر إلى ذاكرة هاتف الباحث. `pack` يُخرج zip يسلّمه الباحث عبر أداة تسليم الملفات (`present_files`/`SendUserFile`) ويرفعه في الجلسة التالية (`load` ← `unpack` ← `validate`). لا اعتماد على Google Drive أو غيره؛ يُذكر خياراً فقط إن طلبه الباحث.

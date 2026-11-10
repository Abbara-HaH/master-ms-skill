# مصدر نسخة humanizer المحفوظة هنا

- المستودع: https://github.com/blader/humanizer
- الرخصة: MIT (نص الرخصة في `LICENSE` كما جُلب، وإشعار حقوق النشر محفوظ فيه)
- الإصدار المعلَن في frontmatter الملف `SKILL.md`: **3.1.0** (`metadata.version`)
- تاريخ الجلب: **2026-11-08** (UTC)
- روابط الجلب (الفرع الرئيس، خام):
  - https://raw.githubusercontent.com/blader/humanizer/refs/heads/main/SKILL.md
  - https://raw.githubusercontent.com/blader/humanizer/refs/heads/main/LICENSE
  - https://raw.githubusercontent.com/blader/humanizer/refs/heads/main/README.md
- كل ملف جُلب بحالة HTTP 200 وحُفظ دون أي تعديل في **المحتوى**.
- **إعادة تسمية واحدة (اسم الملف فقط):** المصدر `SKILL.md` يُحفظ هنا باسم `SKILL.upstream.md`، لأن claude.ai وواجهة Skills API ترفضان أي حزمة فيها أكثر من ملف `SKILL.md` (رسالة `quick_validate`). البصمة أعلاه لم تتغير؛ أي مقارنة مع المستودع تتم بعد إعادة الاسم إلى `SKILL.md`. هذا انحراف عن حرف تعليمات البناء («نسخة مصدر humanizer كما هي») حفاظاً على قابلية التثبيت.

## بصمات الملفات (sha256) وقت الجلب

| الملف | sha256 |
|---|---|
| SKILL.upstream.md (جُلب باسم SKILL.md) | 0612f1dfb1672b0ea9b97e139bf1f06cabe98d8b27424fe8ff01e1fb4cc99cad |
| LICENSE | 4ac4810254ab36d45419141aeb8e69bf50652cfafe5b2dab947d06d44e5cbf96 |
| README.md | 500b53c0d29cd3219d160b5f9a109c0969f706aec74b49a4a081d2026ba48ec7 |

## ما لم يتحقق منه

- **رقم الـ commit غير مسجَّل**: محاولة قراءته من واجهة GitHub API رُفضت بسبب حد المعدّل (HTTP 403)، ولم يُلتفّ على ذلك. الإصدار هنا مأخوذ من الملف نفسه لا من وسم (tag) في المستودع.
- لم يُقارَن الإصدار بوسوم المستودع (releases)؛ للتحقق من وجود إصدار أحدث يُراجَع المستودع يدوياً قبل تحديث هذه النسخة.

## قواعد التعامل مع هذا المجلد

1. الملفات الثلاثة للقراءة فقط؛ لا تُعدَّل ولا تُعاد صياغتها.
2. التكييف العربي في `../humanizer_patterns_ar.md` وقواعد اللينتر في `../../scripts/style_rules.json`، ولا يُكتب شيء منهما داخل هذا المجلد.
3. الملف `SKILL.upstream.md` هنا **مرجع** لا مهارة مستقلة: لا يُستدعى بالأمر `/humanizer`، وعند التعارض بين نصه وبين الأحكام H1–H12 أو الدليل تُقدَّم الأحكام والدليل (انظر قسم «قيود الدمج» في `../anti_ai_style.md`).
4. عند التحديث: اجلب الملفات من جديد، سجّل الإصدار وبصمات الملفات والتاريخ هنا، ثم راجع `humanizer_patterns_ar.md` نمطاً نمطاً لأن الترقيم قد يتغير.

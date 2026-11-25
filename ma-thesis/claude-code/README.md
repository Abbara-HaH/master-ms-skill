# التثبيت في Claude Code

## المهارة المستقلة

```bash
bash claude-code/install.sh              # للمستخدم: ~/.claude/skills و~/.claude/agents
bash claude-code/install.sh --project    # للمشروع الحالي: ./.claude
bash claude-code/install.sh --uninstall
```

بعد التثبيت أعد تشغيل Claude Code ثم استخدم `/ma-thesis`. الوكلاء الفرعيون يظهرون بأسماء `ma-thesis-verifier` و`ma-thesis-critic` و`ma-thesis-integrity` (والمتحقق وحده يملك أدوات الويب؛ الآخران `Read` فقط).

صيغة الوكلاء الفرعيين (frontmatter: name وdescription إلزاميان، وtools اختياري، والمسار `~/.claude/agents/`) من وثائق Claude Code الرسمية. **لم يُختبر المثبّت داخل Claude Code فعلياً**، بل في مجلد HOME معزول (انظر `TESTS.md`).

## الإضافة من سوق Claude Code

يمكن تثبيت الإضافة مباشرة من مستودع GitHub:

```text
/plugin marketplace add Abbara-HaH/master-ms-skill
/plugin install ma-thesis@master-ms-skill
```

بعد التثبيت استخدم `/ma-thesis:full <عنوان البحث أو فكرته>`. يحمّل هذا المدخل `SKILL.md` ومسار الكتابة الكامل وخرائط الفصول مباشرةً. البديل المكافئ هو `/ma-thesis:ma-thesis full <العنوان>`. للتحقق البنيوي شغّل `python3 ma-thesis/scripts/validate_plugin.py`. لم يُختبر تنفيذ هذا الأمر داخل Claude Code فعلياً في هذه البيئة لعدم توفر CLI.

في claude.ai (غير Claude Code) لا يوجد تثبيت دائم للمهارات بهذه الطريقة؛ بدائلها: رفع الحزمة في الجلسة، أو صفحة وحدة الوكلاء المبنية بـ`tools/build_console.py`.

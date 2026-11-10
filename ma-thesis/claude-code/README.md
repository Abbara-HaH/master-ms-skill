# التثبيت في Claude Code

```bash
bash claude-code/install.sh              # للمستخدم: ~/.claude/skills و~/.claude/agents
bash claude-code/install.sh --project    # للمشروع الحالي: ./.claude
bash claude-code/install.sh --uninstall
```

بعد التثبيت أعد تشغيل Claude Code ثم `/ma-thesis`. الوكلاء الفرعيون يظهرون بأسماء `ma-thesis-verifier` و`ma-thesis-critic` و`ma-thesis-integrity` (والمتحقق وحده يملك أدوات الويب؛ الآخران `Read` فقط).

صيغة الوكلاء الفرعيين (frontmatter: name وdescription إلزاميان، وtools اختياري، والمسار `~/.claude/agents/`) من وثائق Claude Code الرسمية. **لم يُختبر المثبّت داخل Claude Code فعلياً**، بل في مجلد HOME معزول (انظر `TESTS.md`).

في claude.ai (غير Claude Code) لا يوجد تثبيت دائم للمهارات بهذه الطريقة؛ بدائلها: رفع الحزمة في الجلسة، أو صفحة وحدة الوكلاء المبنية بـ`tools/build_console.py`.

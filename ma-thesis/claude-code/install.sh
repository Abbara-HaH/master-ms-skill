#!/usr/bin/env bash
# تثبيت ma-thesis في Claude Code: المهارة ← ~/.claude/skills/ma-thesis ، والوكلاء الفرعيون ← ~/.claude/agents/
# الاستخدام:  bash claude-code/install.sh [--uninstall] [--project]
#   --project  يثبّت في ./.claude بدل ~/.claude (للمشروع الحالي فقط)
#   CLAUDE_HOME=/مسار يغيّر الجذر (للاختبار)
# يولّد ملفات الوكلاء الفرعيين من agents/*.md بإضافة frontmatter فقط؛ الأصول تبقى حرفية.
set -euo pipefail
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="${CLAUDE_HOME:-$HOME/.claude}"
[[ "${*}" == *--project* ]] && ROOT="$PWD/.claude"
SK="$ROOT/skills/ma-thesis"; AG="$ROOT/agents"
NAMES=(ma-thesis-verifier ma-thesis-critic ma-thesis-integrity)

if [[ "${*}" == *--uninstall* ]]; then
  chmod -R u+w "$SK" 2>/dev/null || true; rm -rf "$SK"
  for n in "${NAMES[@]}"; do rm -f "$AG/$n.md"; done
  echo "أُزيل ma-thesis من $ROOT"; exit 0
fi

command -v python3 >/dev/null || { echo "يلزم python3 (السكربتات)"; exit 1; }
python3 "$SRC/scripts/guide_verify.py" "$SRC" >/dev/null || { echo "فشل: أجزاء الدليل لا تطابق الأصل؛ لن أثبّت"; exit 1; }

mkdir -p "$ROOT/skills" "$AG"
[[ -d "$SK" ]] && { chmod -R u+w "$SK"; rm -rf "$SK"; }
cp -R "$SRC" "$SK"
rm -rf "$SK/.git" "$SK/TESTS.md.bak" 2>/dev/null || true
find "$SK" -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
chmod a-w "$SK"/references/guide/G*.md "$SK"/references/humanizer_upstream/{SKILL.upstream.md,LICENSE,README.md}

gen() {  # الاسم | الوصف | الأدوات | ملف المصدر
  { printf -- '---\nname: %s\ndescription: "%s"\ntools: %s\n---\n' "$1" "$2" "$3"; cat "$SRC/agents/$4.md"; } > "$AG/$1.md"
}
gen ma-thesis-verifier  "يتحقق من مرجع بحثي وادعاء منسوب إليه (V1–V6) ويعيد JSON بحالة المصدر. استدعِه من ma-thesis فقط، بمرجع وادعاء دون المسودة." "WebSearch, WebFetch, Read" verifier
gen ma-thesis-critic    "لجنة مناقشة صارمة: ينقد نص أطروحة علمياً ومنهجياً ويعيد اعتراضات JSON مرتبة بالخطورة. استدعِه من ma-thesis review دون المحادثة." "Read" critic
gen ma-thesis-integrity "يفحص نزاهة نص أطروحة (M1–M7 وسلسلة T1) ويعيد حكم CLEAR/SUSPECTED/BLOCKED بـJSON. استدعِه عند بوابتي G-A وG-B." "Read" integrity

python3 "$SK/scripts/guide_verify.py" "$SK" >/dev/null && echo "✔ الدليل مطابق للأصل في الموضع الجديد"
echo "✔ المهارة: $SK"
for n in "${NAMES[@]}"; do echo "✔ وكيل فرعي: $AG/$n.md"; done
echo "أعد تشغيل Claude Code ثم اكتب: /ma-thesis"

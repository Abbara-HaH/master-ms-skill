#!/usr/bin/env python3
"""Check that the Claude Code plugin command stays wired to the full workflow."""

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE = ROOT.parent / ".claude-plugin" / "marketplace.json"
COMMAND = ROOT / "commands" / "ma-thesis.md"
FULL_COMMAND = ROOT / "commands" / "full.md"
REQUIRED_WORKFLOW_REFERENCES = (
    "references/full_research_workflow.md",
    "references/chapter_architecture_map.md",
    "references/chapter4_5_architecture.md",
    "references/paragraph_sentence_blueprint.md",
    "references/thesis_writing_patterns.md",
)
REQUIRED_GATES = ("S0", "S9", "G-A", "G-B", "H11", "H17")


def main() -> int:
    errors = []
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Invalid plugin manifest: {exc}", file=sys.stderr)
        return 1

    if manifest.get("name") != "ma-thesis":
        errors.append("plugin.json name must remain ma-thesis")

    try:
        marketplace = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Invalid marketplace manifest: {exc}", file=sys.stderr)
        return 1
    entries = [
        plugin
        for plugin in marketplace.get("plugins", [])
        if plugin.get("name") == manifest.get("name")
    ]
    if len(entries) != 1:
        errors.append("marketplace must list ma-thesis exactly once")
    elif entries[0].get("version") != manifest.get("version"):
        errors.append("plugin and marketplace versions must match")

    try:
        command = COMMAND.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Missing plugin command: {exc}", file=sys.stderr)
        return 1

    if "@${CLAUDE_PLUGIN_ROOT}/SKILL.md" not in command:
        errors.append("plugin command must include the canonical SKILL.md")

    try:
        full_command = FULL_COMMAND.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Missing full-workflow plugin command: {exc}", file=sys.stderr)
        return 1

    if "@${CLAUDE_PLUGIN_ROOT}/SKILL.md" not in full_command:
        errors.append("full command must include the canonical SKILL.md")
    for reference in REQUIRED_WORKFLOW_REFERENCES:
        if not (ROOT / reference).is_file():
            errors.append(f"required workflow file is missing: {reference}")
        if f"@${{CLAUDE_PLUGIN_ROOT}}/{reference}" not in full_command:
            errors.append(f"full command must directly include {reference}")
    for gate in REQUIRED_GATES:
        if gate not in full_command:
            errors.append(f"full command must preserve {gate}")

    if errors:
        print("\n".join(f"FAIL: {error}" for error in errors), file=sys.stderr)
        return 1

    print("Plugin command is wired to the canonical skill and full workflow.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

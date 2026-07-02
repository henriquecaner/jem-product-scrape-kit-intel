"""Toolchain green check + 'kit for IT' rendering (onboarding §6 Fase A)."""
from dataclasses import dataclass


@dataclass
class Tool:
    name: str          # executable to look up
    label: str         # human label
    winget_id: str     # winget package id for the IT kit ("" = no winget install)
    why: str
    required: bool     # blocks readiness vs optional (browser path)


TOOLS = (
    Tool("git", "Git", "Git.Git", "version control + resume checkpoints", True),
    Tool("gh", "GitHub CLI", "GitHub.cli", "gh secret set / repo ops (Actions runtime)", True),
    Tool("python3", "Python 3", "Python.Python.3.12", "runs the scraper engine", True),
    Tool("playwright", "Playwright", "",
         "browser render path for SPA/JS sites — pip install playwright && playwright install chromium",
         False),
)


def check_tools(*, which, tools=TOOLS):
    found = {t.name: bool(which(t.name)) for t in tools}
    present = [t for t in tools if found[t.name]]
    missing = [t for t in tools if not found[t.name]]
    ready = all(found[t.name] for t in tools if t.required)
    return {"ready": ready, "present": present, "missing": missing}


def render_it_kit(report):
    missing = report.get("missing", [])
    winget = [t for t in missing if t.winget_id]
    manual = [t for t in missing if not t.winget_id]
    if not winget and not manual:
        return ""
    lines = ["# Kit para a TI — instalar de uma vez", ""]
    if winget:
        lines += ["Rode como administrador (PowerShell):", "", "```powershell"]
        for t in winget:
            lines.append(f"winget install --id {t.winget_id} -e --silent   # {t.label}: {t.why}")
        lines += ["```", ""]
    if manual:
        lines.append("Passos manuais:")
        for t in manual:
            lines.append(f"- {t.label}: {t.why}")
    return "\n".join(lines)

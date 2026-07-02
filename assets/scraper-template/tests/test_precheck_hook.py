import json
import subprocess
import sys
from pathlib import Path

# hooks/scripts/precheck.py lives at the plugin repo root (tests -> scraper-template
# -> assets -> repo root). Invoke it as a subprocess with a simulated PreToolUse event.
HOOK = Path(__file__).resolve().parents[3] / "hooks" / "scripts" / "precheck.py"


def _run(event):
    p = subprocess.run([sys.executable, str(HOOK)],
                       input=json.dumps(event), capture_output=True, text=True)
    return p.returncode, p.stderr


def test_blocks_git_add_of_authorization_secret():
    rc, err = _run({"tool_name": "Bash",
                    "tool_input": {"command": "git add .scrape-authorization.json"}})
    assert rc == 2
    assert ".scrape-authorization.json" in err


def test_blocks_git_commit_touching_env_file():
    rc, err = _run({"tool_name": "Bash",
                    "tool_input": {"command": "git commit -m wip .env"}})
    assert rc == 2


def test_blocks_git_add_warmup_verdict_secret():
    rc, err = _run({"tool_name": "Bash",
                    "tool_input": {"command": "git add .scrape-warmup.json"}})
    assert rc == 2


def test_allows_normal_git_add_of_exports():
    rc, _ = _run({"tool_name": "Bash", "tool_input": {"command": "git add exports/"}})
    assert rc == 0


def test_allows_non_git_bash_command():
    rc, _ = _run({"tool_name": "Bash",
                  "tool_input": {"command": "cat .scrape-authorization.json"}})
    assert rc == 0  # reading is fine; only git staging is guarded


def test_allows_non_bash_tool():
    rc, _ = _run({"tool_name": "Read",
                  "tool_input": {"file_path": ".scrape-authorization.json"}})
    assert rc == 0


def test_allows_unparseable_event():
    p = subprocess.run([sys.executable, str(HOOK)],
                       input="{not json", capture_output=True, text=True)
    assert p.returncode == 0

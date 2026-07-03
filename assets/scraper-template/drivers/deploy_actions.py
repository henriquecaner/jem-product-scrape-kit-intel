"""Deploy the Actions workflow for a scraped project (onboarding §6.1). Builds the
gh commands that set the gate secrets from local files — the secret value is piped
via stdin, NEVER placed on argv (which would leak it into process listings)."""
from pathlib import Path

_SECRET_MAP = (
    ("SCRAPE_AUTHORIZATION", ".scrape-authorization.json"),
    ("SCRAPE_WARMUP", ".scrape-warmup.json"),
    ("SCRAPE_STORAGE_STATE", ".scrape-session.json"),
)


def build_secret_commands(project_dir, *, secret_map=_SECRET_MAP):
    project_dir = Path(project_dir)
    steps = []
    for name, filename in secret_map:
        f = project_dir / filename
        if f.exists():
            steps.append({
                "secret": name,
                "argv": ["gh", "secret", "set", name],
                "stdin_file": f,
            })
    return steps

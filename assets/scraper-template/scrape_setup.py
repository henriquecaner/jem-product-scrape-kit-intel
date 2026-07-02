"""Backing for /scrape-setup (onboarding §6 Fase B): green check + Desktop PATH
fix + readiness gate. Exit 0 when ready, 1 when a required tool is missing."""
import argparse
import os
import shutil
import sys

from jemscrape.toolchain import check_tools, render_it_kit
from jemscrape.settings_patch import patch_claude_settings


def main(argv=None, *, which=None, settings_path=None, path_env=None):
    parser = argparse.ArgumentParser(description="Scraper onboarding: green check + PATH fix")
    parser.add_argument("--settings", default=None, help="path to ~/.claude/settings.json")
    args = parser.parse_args(argv)

    which = shutil.which if which is None else which
    report = check_tools(which=which)

    print("[setup] toolchain:")
    for t in report["present"]:
        print(f"  OK   {t.label}")
    for t in report["missing"]:
        print(f"  MISS {t.label} ({'REQUIRED' if t.required else 'optional'})")

    settings = args.settings or settings_path
    if settings:
        env = path_env if path_env is not None else {"PATH": os.environ.get("PATH", "")}
        patch_claude_settings(settings, env=env)
        print(f"[setup] wrote PATH env to {settings}")

    if not report["ready"]:
        kit = render_it_kit(report)
        if kit:
            print("\n" + kit, file=sys.stderr)
        print("[setup] NOT READY - install the required tools above, then re-run.", file=sys.stderr)
        return 1
    print("[setup] READY - you can run /scrape-init.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

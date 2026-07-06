"""CLI: render docs/run-plan.md to HTML + PDF (PDF when Chrome is available)."""
import argparse
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render the run-plan to HTML/PDF")
    parser.add_argument("--markdown", default="docs/run-plan.md")
    parser.add_argument("--out", default="docs")
    args = parser.parse_args(argv)
    from drivers.render_pdf import render_pdf
    result = render_pdf(args.markdown, args.out)
    if result["pdf"]:
        print(f"[run-plan] PDF -> {result['pdf']}")
    else:
        print(f"[run-plan] Chrome not found — HTML fallback -> {result['html']}",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

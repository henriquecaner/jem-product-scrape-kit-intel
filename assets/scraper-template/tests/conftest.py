import sys
from pathlib import Path

# Make the template package importable when tests run from the repo root.
TEMPLATE_ROOT = Path(__file__).resolve().parent.parent
if str(TEMPLATE_ROOT) not in sys.path:
    sys.path.insert(0, str(TEMPLATE_ROOT))

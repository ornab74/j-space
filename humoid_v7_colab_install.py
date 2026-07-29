"""One-cell installer for Humoid V7 repository management.

Use from the V6 notebook after class-definition cells:

    !wget -q https://raw.githubusercontent.com/ornab74/j-space/main/humoid_v7_colab_install.py -O /content/humoid_v7_colab_install.py
    %run /content/humoid_v7_colab_install.py
"""

from pathlib import Path
import importlib.util
import urllib.request

MODULE_URL = (
    "https://raw.githubusercontent.com/ornab74/j-space/"
    "main/humoid_v7_repo_management.py"
)
MODULE_PATH = Path("/content/humoid_v7_repo_management.py")

# Always refresh the small compatibility module so a resumed Colab runtime gets
# the latest repository-management fixes from main.
urllib.request.urlretrieve(MODULE_URL, MODULE_PATH)

spec = importlib.util.spec_from_file_location(
    "humoid_v7_repo_management",
    MODULE_PATH,
)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load {MODULE_PATH}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

namespace = globals()
namespace.setdefault("CODING_REPO_PACKAGE_NAME", "humoid_quantum")
namespace.setdefault("CODE_REPO_SOURCE_URL", "")
namespace.setdefault("CODE_REPO_SOURCE_REF", "main")
namespace.setdefault("CODING_REPO_CREATE_BASELINE_COMMIT", True)

V7_REPORT = module.install_humoid_v7(
    namespace,
    reset_invalid_state=True,
)
namespace["V7_REPORT"] = V7_REPORT

print("\nNext: rerun cells 11B, 11C, 11A, then the scheduler with resume=True.")

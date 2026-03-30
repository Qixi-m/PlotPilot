"""保证从仓库内任意 cwd 运行 pytest 时能找到包 aitext。"""
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
_parent = _root.parent
if str(_parent) not in sys.path:
    sys.path.insert(0, str(_parent))

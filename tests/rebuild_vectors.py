"""重建当前项目所有记忆的向量(用最新 embed_text 逻辑)。

切换 embedding 模型或 embed_text 逻辑后跑此脚本,重新 embed 全部记忆。
用法:在项目根或 ai_agent_memory_mcp 目录下 `python tests/rebuild_vectors.py`
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))

from ai_agent_memory_mcp.config import find_project_root
from ai_agent_memory_mcp.server import init_service, _svc

init_service(find_project_root(), "rebuild")
svc = _svc()
mems = svc.store.list()
print(f"rebuilding vectors for {len(mems)} memories in {svc.config.data_dir}")
for m in mems:
    svc.vector.upsert(m)  # 用新 embed_text(title+tags+content)
print("done")

"""端到端验证:remember + recall + list + forget(需 VOLCENGINE_API_KEY)。

从 cwd 向上查找 .env 读 key;无 key 则跳过。
直接调用 service 层(绕过 MCP stdio),验证 SQLite+Chroma+Markdown+embedding 全链路。
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))

if not os.getenv("VOLCENGINE_API_KEY"):
    print("SKIP: 未找到 VOLCENGINE_API_KEY(在 .env 或环境变量中配置)")
    print("      配置后重跑本脚本验证端到端。")
    sys.exit(0)

from ai_memory.server import init_service, remember, recall, list_memories, forget

init_service(Path(tempfile.mkdtemp()), "e2e-test")

print(">> remember 1 (project)")
r1 = remember(
    title="FAISS 向量检索",
    content="FAISS 是 Facebook 开源的高维向量近似检索库,支持 ANN 搜索",
    category="project", tags=["vector", "检索"],
)
print("   ", r1)

print(">> remember 2 (user)")
r2 = remember(
    title="用户偏好:中文回答",
    content="用户希望用中文回答,代码注释也用中文",
    category="user",
)
print("   ", r2)

print(">> recall '向量搜索'")
res = recall(query="向量搜索", top_k=2)
for m in res:
    print("   hit:", m["id"], "|", m["title"])
    verr = (m.get("metadata") or {}).get("vector_error")
    if verr:
        print("   ⚠ vector_error:", verr)

print(">> list_memories")
print("   ", [m["title"] for m in list_memories()])

print(">> forget r1")
forget(r1["id"])

if res:
    print("PASS: remember/recall/list/forget 链路正常")
else:
    print("WARN: recall 无结果(检查 embedding 是否可用)")

"""
embedding.py —— 文本转向量 + 记忆库语义检索

模型: BAAI/bge-small-zh-v1.5 (约100MB,CPU 可跑,首次运行自动从镜像下载)

职责与规范:
- 本模块不 import tools / Model_Function;记忆条目格式与 tools.py 约定同步("- [时间] 内容"),
  两边的解析规则要一起改
- 路径一律从 Store 拿
- 索引产物:memory_vectors.npy(向量矩阵,第 i 行对应第 i 条) + memory_index.json(时间/原文,按行对齐)
- 更新策略:检索前检测索引是否过期(条目数变了/记忆文件比索引新),过期就全量重建
  (几百条秒级;增量对齐在删改场景麻烦,全量重建天然正确)

函数结构:
├─ text_to_vector(text)          单句 → 归一化向量(512,)
├─ embed_build()                 全量建库:读记忆条目 → 批量编码 → 存 .npy + json,返回条数
├─ embed_search(query, top_k)    语义检索:点积取最近 top_k,索引过期自动重建
├─ _read_entries()               内部:解析 memory.md 条目(格式与 tools 同步)
├─ _index_stale()                内部:索引是否需要重建
└─ _get_model()                  内部:懒加载
"""
import os
import json
# 镜像必须在 sentence_transformers 被 import 之前设置才生效
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

import numpy as np
from sentence_transformers import SentenceTransformer

from .Store import Store

MODEL_NAME = "BAAI/bge-small-zh-v1.5"

_model = None   # 模型缓存,进程内只加载一次


def _get_model():
    """内部:懒加载模型,第一次调用慢几秒,之后微秒级复用"""
    global _model
    if _model is None:
        print(f"[embedding] 正在加载模型 {MODEL_NAME} ...")
        _model = SentenceTransformer(MODEL_NAME)
        print("[embedding] 模型加载完成")
    return _model


def text_to_vector(text):
    """单句接口:一段文本 → 一个归一化向量(numpy 一维数组)"""
    if not text or not str(text).strip():
        print("[embedding] 输入为空,返回零向量")
        return np.zeros(_get_model().get_sentence_embedding_dimension())
    vec = _get_model().encode(str(text).strip(), normalize_embeddings=True)
    return np.asarray(vec)


# ==================== 记忆库建库与检索 ====================
def _read_entries():
    """内部:解析记忆条目,返回 [(时间, 内容), ...]
    解析规则与 tools.memory_read 同步:只认行首 '- [' 的行,其余跳过"""
    entries = []
    if not os.path.exists(Store.MEMORY_FILE):
        return entries
    with open(Store.MEMORY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("- [") or "]" not in line:
                continue
            body = line[3:]                      # 去掉 "- ["
            stamp, content = body.split("]", 1)
            entries.append((stamp.strip(), content.strip()))
    return entries


def _index_stale():
    """内部:索引不存在 / 条目数对不上 / 记忆文件比索引新 → 需要重建"""
    if not os.path.exists(Store.MEMORY_VECTOR_FILE) or not os.path.exists(Store.MEMORY_INDEX_FILE):
        return True
    try:
        with open(Store.MEMORY_INDEX_FILE, "r", encoding="utf-8") as f:
            index = json.load(f)
    except (json.JSONDecodeError, OSError):
        return True
    if len(index) != len(_read_entries()):
        return True
    return os.path.getmtime(Store.MEMORY_FILE) > os.path.getmtime(Store.MEMORY_INDEX_FILE)


def embed_build():
    """全量建库:读记忆条目 → 批量编码 → 存向量矩阵+元数据。返回条目数(空库会清掉旧索引)"""
    entries = _read_entries()
    if not entries:
        for path in (Store.MEMORY_VECTOR_FILE, Store.MEMORY_INDEX_FILE):
            if os.path.exists(path):
                os.remove(path)
        print("[embedding] 记忆库为空,索引已清空")
        return 0
    contents = [content for _, content in entries]
    vecs = _get_model().encode(contents, normalize_embeddings=True, show_progress_bar=False)
    np.save(Store.MEMORY_VECTOR_FILE, np.asarray(vecs))
    with open(Store.MEMORY_INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump([{"time": t, "content": c} for t, c in entries], f, ensure_ascii=False, indent=2)
    print(f"[embedding] 建库完成:{len(entries)} 条 → {Store.MEMORY_VECTOR_FILE}")
    return len(entries)


def embed_search(query, top_k=5):
    """语义检索:query 和全库条目算余弦相似度,取最近 top_k。

    返回 [(相似度, 时间, 内容), ...] 按相似度降序;库空返回 []
    注意:bge 的相似度分布偏窄,判断相关看排序和差值,别设"必须>0.5"之类的硬阈值
    """
    if _index_stale():
        embed_build()
    if not os.path.exists(Store.MEMORY_VECTOR_FILE):
        return []
    with open(Store.MEMORY_INDEX_FILE, "r", encoding="utf-8") as f:
        index = json.load(f)
    if len(index) == 0:
        return []
    vecs = np.load(Store.MEMORY_VECTOR_FILE)
    q = text_to_vector(query)
    sims = vecs @ q                                 # 双方都已归一化,点积 = 余弦相似度
    order = np.argsort(-sims)[:top_k]
    return [(float(sims[i]), index[i]["time"], index[i]["content"]) for i in order]


# ==================== 自测(直接运行本文件才会执行) ====================
if __name__ == "__main__":
    import tempfile
    # 自测时把 Store 的路径指到临时目录,绝不碰真实记忆
    tmp = tempfile.mkdtemp()
    Store.MEMORY_FILE = os.path.join(tmp, "memory.md")
    Store.MEMORY_VECTOR_FILE = os.path.join(tmp, "memory_vectors.npy")
    Store.MEMORY_INDEX_FILE = os.path.join(tmp, "memory_index.json")

    # 造测试记忆(四条不同主题)
    with open(Store.MEMORY_FILE, "w", encoding="utf-8") as f:
        f.write("# 长期记忆\n\n")
        f.write("- [2026-09-27 10:00] 用户主板串口坏了\n")
        f.write("- [2026-09-27 10:01] 用户在备考四级英语\n")
        f.write("- [2026-09-27 10:02] 项目使用 DeepSeek API 调用大模型\n")

    n = embed_build()
    print("建库条数:", n)
    print("检索『电脑坏了』:", embed_search("电脑坏了", top_k=2)[0][2])
    print("检索『英语考试』:", embed_search("英语考试", top_k=2)[0][2])
    print("检索『AI接口』:", embed_search("AI接口", top_k=2)[0][2])

    # 新鲜度:追加一条后,下次检索应自动重建并命中新条目
    with open(Store.MEMORY_FILE, "a", encoding="utf-8") as f:
        f.write("- [2026-09-27 10:03] 用户在学 STM32 单片机\n")
    print("追加后自动重建,检索『单片机开发板』:", embed_search("单片机开发板", top_k=1)[0][2])
    print("自测完成")

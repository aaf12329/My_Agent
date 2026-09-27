"""
embedding.py —— 文本转向量(最小接口版)

模型: BAAI/bge-small-zh-v1.5 (约100MB,CPU 可跑,首次运行自动从镜像下载)
用法:
    from tool.embedding import text_to_vector
    vec = text_to_vector("你好")     # 返回 numpy 一维向量,形状 (512,)

约定:
1. 返回的向量已做归一化 → 以后算相似度直接点积 vec_a @ vec_b,结果就是余弦相似度
2. 模型只加载一次(懒加载),第一次调用慢几秒,之后微秒级复用
"""
import os
# 镜像必须在 sentence_transformers 被 import 之前设置才生效
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = "BAAI/bge-small-zh-v1.5"

_model = None   # 模型缓存,进程内只加载一次


def _get_model():
    """内部:懒加载模型"""
    global _model
    if _model is None:
        print(f"[embedding] 正在加载模型 {MODEL_NAME} ...")
        _model = SentenceTransformer(MODEL_NAME)
        print("[embedding] 模型加载完成")
    return _model


def text_to_vector(text):
    """唯一接口:一段文本 → 一个向量(numpy 一维数组,已归一化)"""
    if not text or not str(text).strip():
        print("[embedding] 输入为空,返回零向量")
        return np.zeros(_get_model().get_sentence_embedding_dimension())
    vec = _get_model().encode(str(text).strip(), normalize_embeddings=True)
    return np.asarray(vec)


# ==================== 自测(直接运行本文件才会执行) ====================
if __name__ == "__main__":
    v1 = text_to_vector("帮我看看这段代码为什么报错")
    v2 = text_to_vector("这个程序跑不起来")
    v3 = text_to_vector("今天天气不错")

    print("向量维度:", v1.shape)                        # 期望 (512,)
    print("代码 vs 程序(意思近):", round(float(v1 @ v2), 3))   # 期望 0.6~0.8
    print("代码 vs 天气(意思远):", round(float(v1 @ v3), 3))   # 期望接近 0
    print("自测完成")

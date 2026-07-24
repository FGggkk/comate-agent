import httpx

from app.config.settings import get_settings

settings = get_settings()


async def get_embedding(text: str) -> list[float] | None:
    """调用阿里云百炼 text-embedding-v4 生成向量"""
    if not settings.dashscope_api_key or not settings.dashscope_workspace_id:
        print("[embedding] API Key 或 Workspace ID 未配置")
        return None

    base_url = f"https://{settings.dashscope_workspace_id}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                f"{base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {settings.dashscope_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.embedding_model,
                    "input": text,
                    "dimensions": settings.embedding_dimensions,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0]["embedding"]
        except Exception as e:
            print(f"[embedding] 调用失败: {e}")
            return None


async def get_embeddings_batch(texts: list[str]) -> list[list[float]] | None:
    """批量生成向量"""
    if not texts:
        return []

    if not settings.dashscope_api_key or not settings.dashscope_workspace_id:
        print("[embedding] API Key 或 Workspace ID 未配置")
        return None

    base_url = f"https://{settings.dashscope_workspace_id}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(
                f"{base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {settings.dashscope_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.embedding_model,
                    "input": texts,
                    "dimensions": settings.embedding_dimensions,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return [item["embedding"] for item in data["data"]]
        except Exception as e:
            print(f"[embedding] 批量调用失败: {e}")
            return None

import uuid
from datetime import datetime

from qcloud_cos import CosConfig, CosS3Client

from app.config.settings import get_settings

settings = get_settings()


def _get_client() -> CosS3Client | None:
    if not settings.cos_secret_id or not settings.cos_secret_key:
        return None
    config = CosConfig(
        Region=settings.cos_region,
        SecretId=settings.cos_secret_id,
        SecretKey=settings.cos_secret_key,
    )
    return CosS3Client(config)


def upload_avatar(file_bytes: bytes, filename: str, user_id: str) -> str | None:
    """
    上传头像到 COS，返回可访问的 URL

    路径规则: avatars/{user_id}/{timestamp}_{uuid}.{ext}
    """
    client = _get_client()
    if not client:
        return None

    # 提取扩展名
    ext = "png"
    if "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext not in ("jpg", "jpeg", "png", "gif", "webp"):
            ext = "png"

    # 构造路径: avatars/{user_id}/{timestamp}_{uuid}.{ext}
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    uid = uuid.uuid4().hex[:8]
    key = f"avatars/comate/{user_id}/{ts}_{uid}.{ext}"

    try:
        resp = client.put_object(
            Bucket=settings.cos_bucket,
            Body=file_bytes,
            Key=key,
            ContentType=f"image/{ext}",
        )
        if resp.get("ETag"):
            # 返回 CDN/源站 URL
            return f"https://{settings.cos_bucket}.cos.{settings.cos_region}.myqcloud.com/{key}"
        return None
    except Exception as e:
        print(f"[COS upload error] {e}")
        return None


def upload_image(file_bytes: bytes, filename: str, folder: str = "souls") -> str | None:
    """
    通用图片上传（角色卡面图/头像图等）
    路径规则: {folder}/{timestamp}_{uuid}.{ext}
    """
    client = _get_client()
    if not client:
        return None

    ext = "png"
    if "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext not in ("jpg", "jpeg", "png", "gif", "webp"):
            ext = "png"

    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    uid = uuid.uuid4().hex[:8]
    key = f"{folder}/comate/{ts}_{uid}.{ext}"

    try:
        resp = client.put_object(
            Bucket=settings.cos_bucket,
            Body=file_bytes,
            Key=key,
            ContentType=f"image/{ext}",
        )
        if resp.get("ETag"):
            return f"https://{settings.cos_bucket}.cos.{settings.cos_region}.myqcloud.com/{key}"
        return None
    except Exception as e:
        print(f"[COS upload error] {e}")
        return None

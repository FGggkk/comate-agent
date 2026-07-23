from dataclasses import dataclass, field


@dataclass
class ModelConfig:
    provider: str = "deepseek"
    model: str = "deepseek-chat"
    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    stream: bool = True
    max_tokens: int = 4096
    temperature: float = 0.7


def get_model_config() -> ModelConfig:
    from app.config.settings import get_settings

    s = get_settings()
    return ModelConfig(
        api_key=s.deepseek_api_key,
        base_url=s.deepseek_base_url,
        model=s.deepseek_model,
    )

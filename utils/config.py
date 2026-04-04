import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Literal
from dotenv import load_dotenv

load_dotenv()

LLMProvider = Literal["modelscope", "openrouter"]


@dataclass
class Config:
    llm_base_url: str
    llm_model: str
    llm_api_key: str
    llm_provider: LLMProvider
    storage_dir: Path
    chroma_dir: Path
    pdf_dir: Path
    parsed_dir: Path
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    
    # OpenRouter 备用配置
    openrouter_base_url: str = ""
    openrouter_model: str = ""
    openrouter_api_key: str = ""


_config: Optional[Config] = None


def get_config(provider: Optional[LLMProvider] = None) -> Config:
    """获取配置
    
    Args:
        provider: 指定 LLM 提供商，None 使用环境变量 LLM_PROVIDER 或默认 modelscope
    """
    global _config
    
    # 确定使用哪个 provider
    use_provider = provider or os.getenv("LLM_PROVIDER", "openrouter")
    
    if _config is None or _config.llm_provider != use_provider:
        storage_dir = Path(__file__).parent.parent / "storage"
        
        # OpenRouter 配置
        openrouter_base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        openrouter_model = os.getenv("OPENROUTER_MODEL", "qwen/qwen3.6-plus:free")
        openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")
        
        # ModelScope 配置
        modelscope_base_url = os.getenv("OPENAI_COMPAT_BASE_URL", "https://api-inference.modelscope.cn/v1")
        modelscope_model = os.getenv("OPENAI_COMPAT_MODEL", "Qwen/Qwen3.5-27B")
        modelscope_api_key = os.getenv("OPENAI_COMPAT_API_KEY", "")
        
        # 根据 provider 选择配置
        if use_provider == "openrouter":
            base_url = openrouter_base_url
            model = openrouter_model
            api_key = openrouter_api_key
        else:
            base_url = modelscope_base_url
            model = modelscope_model
            api_key = modelscope_api_key
        
        _config = Config(
            llm_base_url=base_url,
            llm_model=model,
            llm_api_key=api_key,
            llm_provider=use_provider,
            storage_dir=storage_dir,
            chroma_dir=storage_dir / "chroma",
            pdf_dir=storage_dir / "pdfs",
            parsed_dir=storage_dir / "parsed",
            openrouter_base_url=openrouter_base_url,
            openrouter_model=openrouter_model,
            openrouter_api_key=openrouter_api_key,
        )
    return _config

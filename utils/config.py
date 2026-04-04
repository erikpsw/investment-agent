import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    llm_base_url: str
    llm_model: str
    llm_api_key: str
    storage_dir: Path
    chroma_dir: Path
    pdf_dir: Path
    parsed_dir: Path
    embedding_model: str = "BAAI/bge-small-zh-v1.5"


_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        storage_dir = Path(__file__).parent.parent / "storage"
        _config = Config(
            llm_base_url=os.getenv("OPENAI_COMPAT_BASE_URL", "https://api-inference.modelscope.cn/v1"),
            llm_model=os.getenv("OPENAI_COMPAT_MODEL", "Qwen/Qwen3.5-27B"),
            llm_api_key=os.getenv("OPENAI_COMPAT_API_KEY", ""),
            storage_dir=storage_dir,
            chroma_dir=storage_dir / "chroma",
            pdf_dir=storage_dir / "pdfs",
            parsed_dir=storage_dir / "parsed",
        )
    return _config

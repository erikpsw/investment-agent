from typing import Any
import httpx
from ..utils.config import get_config


class LLMClient:
    """LLM 客户端，支持 OpenAI 兼容 API"""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
    ):
        config = get_config()
        self.base_url = base_url or config.llm_base_url
        self.model = model or config.llm_model
        self.api_key = api_key or config.llm_api_key
        
        self.client = httpx.Client(timeout=60.0)

    def chat(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """发送聊天请求
        
        Args:
            prompt: 用户消息
            system_prompt: 系统提示词
            temperature: 温度参数
            max_tokens: 最大生成 token 数
            
        Returns:
            模型回复文本
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        return self.chat_messages(messages, temperature, max_tokens)

    def chat_messages(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """发送多轮对话请求
        
        Args:
            messages: 消息列表 [{"role": "user/assistant/system", "content": "..."}]
            temperature: 温度参数
            max_tokens: 最大生成 token 数
            
        Returns:
            模型回复文本
        """
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        
        try:
            response = self.client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            return f"[LLM 调用失败: {str(e)}]"

    def analyze(
        self,
        data: dict[str, Any],
        task: str,
        format_hint: str = "",
    ) -> str:
        """分析数据并生成报告
        
        Args:
            data: 待分析的数据
            task: 分析任务描述
            format_hint: 输出格式提示
        """
        import json
        
        system_prompt = """你是一位专业的投资分析师。请基于提供的数据进行客观、专业的分析。
注意事项：
1. 区分事实、假设和观点
2. 标注数据来源和时效性
3. 指出潜在风险
4. 分析结果仅供参考，不构成投资建议"""
        
        prompt = f"""## 分析任务
{task}

## 数据
```json
{json.dumps(data, ensure_ascii=False, indent=2)}
```

{format_hint}

请提供专业分析："""
        
        return self.chat(prompt, system_prompt, temperature=0.3)

    def close(self):
        """关闭客户端"""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


_default_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """获取默认 LLM 客户端（单例）"""
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client

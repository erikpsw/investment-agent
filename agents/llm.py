from typing import Any, Optional, List, Dict, Iterator, AsyncIterator
from openai import OpenAI, AsyncOpenAI
from langsmith import traceable, wrappers
from ..utils.config import get_config


class LLMClient:
    """LLM 客户端，支持 OpenAI 兼容 API，集成 LangSmith 追踪"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        config = get_config()
        self.base_url = base_url or config.llm_base_url
        self.model = model or config.llm_model
        self.api_key = api_key or config.llm_api_key
        
        # 用 OpenAI SDK + LangSmith wrap，自动追踪所有调用
        self.client = wrappers.wrap_openai(OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=180.0,
        ))
        self.async_client = wrappers.wrap_openai(AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=180.0,
        ))

    @traceable(name="llm.chat")
    def chat(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        return self.chat_messages(messages, temperature, max_tokens)

    @traceable(name="llm.chat_messages")
    def chat_messages(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            
            if not response.choices:
                return "[LLM 未返回有效回复]"
            
            content = response.choices[0].message.content
            return content or "[LLM 回复内容为空]"
        except Exception as e:
            return f"[LLM 调用失败: {str(e)}]"

    async def chat_stream(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> AsyncIterator[str]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        async for chunk in self.chat_messages_stream(messages, temperature, max_tokens):
            yield chunk

    async def chat_messages_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> AsyncIterator[str]:
        try:
            stream = await self.async_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield f"[LLM 调用失败: {str(e)}]"

    @traceable(name="llm.analyze")
    def analyze(
        self,
        data: dict[str, Any],
        task: str,
        format_hint: str = "",
    ) -> str:
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

    async def analyze_stream(
        self,
        data: dict[str, Any],
        task: str,
        format_hint: str = "",
    ) -> AsyncIterator[str]:
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
        
        async for chunk in self.chat_stream(prompt, system_prompt, temperature=0.3):
            yield chunk

    def close(self):
        self.client.close()

    async def aclose(self):
        await self.async_client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


_default_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """获取默认 LLM 客户端（单例）"""
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client

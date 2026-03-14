from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.config import get_settings


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class ChatCompletionResponse:
    content: str
    model: str
    usage: dict | None = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def chat_completion(
        self, messages: list[ChatMessage], temperature: float = 0.3
    ) -> ChatCompletionResponse:
        """Synchronous chat completion. Call via asyncio.to_thread from async code."""
        ...


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        self.model = model

    def chat_completion(
        self, messages: list[ChatMessage], temperature: float = 0.3
    ) -> ChatCompletionResponse:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
        )
        choice = response.choices[0]
        return ChatCompletionResponse(
            content=choice.message.content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
            },
        )


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        import anthropic

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def chat_completion(
        self, messages: list[ChatMessage], temperature: float = 0.3
    ) -> ChatCompletionResponse:
        system_msg = ""
        chat_messages = []
        for m in messages:
            if m.role == "system":
                system_msg = m.content
            else:
                chat_messages.append({"role": m.role, "content": m.content})

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_msg,
            messages=chat_messages,
            temperature=temperature,
        )
        return ChatCompletionResponse(
            content=response.content[0].text,
            model=response.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        )


class DeepResearchProvider(LLMProvider):
    """OpenAI Responses API with web_search tool for deep research (o4-mini)."""

    def __init__(self, api_key: str, model: str):
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        self.model = model

    def chat_completion(
        self, messages: list[ChatMessage], temperature: float = 0.3
    ) -> ChatCompletionResponse:
        prompt = "\n\n".join(m.content for m in messages)

        response = self.client.responses.create(
            model=self.model,
            input=prompt,
            tools=[{"type": "web_search_preview"}],
        )

        # Extract text from response output items
        output_text = ""
        for item in response.output:
            if item.type == "message":
                for block in item.content:
                    if hasattr(block, "text"):
                        output_text += block.text

        usage = {}
        if hasattr(response, "usage") and response.usage:
            usage = {
                "input_tokens": getattr(response.usage, "input_tokens", 0),
                "output_tokens": getattr(response.usage, "output_tokens", 0),
            }

        return ChatCompletionResponse(
            content=output_text,
            model=self.model,
            usage=usage,
        )


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        self.model_name = model
        self.model = genai.GenerativeModel(model)

    def chat_completion(
        self, messages: list[ChatMessage], temperature: float = 0.3
    ) -> ChatCompletionResponse:
        combined_prompt = ""
        for m in messages:
            combined_prompt += f"{m.content}\n\n"

        response = self.model.generate_content(
            combined_prompt,
            generation_config={"temperature": temperature},
        )
        return ChatCompletionResponse(
            content=response.text,
            model=self.model_name,
        )


def get_llm_provider(provider_name: str | None = None) -> LLMProvider:
    """Factory function. Pass 'openai', 'anthropic'/'claude', or 'gemini'.

    Defaults to LLM_PROVIDER from settings.
    """
    settings = get_settings()
    name = (provider_name or settings.LLM_PROVIDER).lower()

    if name == "openai":
        return OpenAIProvider(api_key=settings.OPENAI_API_KEY, model=settings.OPENAI_MODEL)
    elif name in ("anthropic", "claude"):
        return AnthropicProvider(api_key=settings.ANTHROPIC_API_KEY, model=settings.ANTHROPIC_MODEL)
    elif name in ("deep-research", "deep_research"):
        return DeepResearchProvider(api_key=settings.OPENAI_API_KEY, model=settings.OPENAI_DEEP_RESEARCH_MODEL)
    elif name == "gemini":
        return GeminiProvider(api_key=settings.GEMINI_API_KEY, model=settings.GEMINI_MODEL)
    else:
        raise ValueError(f"Unsupported LLM provider: {name}. Supported: openai, anthropic, gemini, deep-research")

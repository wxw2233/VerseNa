"""模型提供商预设配置"""

PROVIDER_PRESETS = {
    "deepseek": {
        "id": "deepseek",
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "vision_models": [],
        "image_models": [],
        "is_custom": False,
    },
    "openai": {
        "id": "openai",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo", "o1", "o1-mini", "o1-pro"],
        "vision_models": ["gpt-4o", "gpt-4-turbo", "o1"],
        "image_models": ["dall-e-3", "dall-e-2"],
        "is_custom": False,
    },
    "siliconflow": {
        "id": "siliconflow",
        "name": "SiliconFlow",
        "base_url": "https://api.siliconflow.cn/v1",
        "models": [
            "deepseek-ai/DeepSeek-V3",
            "deepseek-ai/DeepSeek-R1",
            "Qwen/Qwen2.5-72B-Instruct",
            "Qwen/Qwen2.5-32B-Instruct",
            "meta-llama/Meta-Llama-3.1-70B-Instruct",
        ],
        "vision_models": ["deepseek-ai/deepseek-vl2", "Qwen/Qwen2.5-VL-72B-Instruct"],
        "image_models": ["stabilityai/stable-diffusion-3-medium", "black-forest-labs/FLUX.1-schnell"],
        "is_custom": False,
    },
    "zhipu": {
        "id": "zhipu",
        "name": "智谱AI",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": ["glm-4-flash", "glm-4-plus", "glm-4", "glm-4-long"],
        "vision_models": ["glm-4v-flash", "glm-4v-plus"],
        "image_models": ["cogview-3-flash", "cogview-3-plus"],
        "is_custom": False,
    },
    "moonshot": {
        "id": "moonshot",
        "name": "Moonshot (月之暗面)",
        "base_url": "https://api.moonshot.cn/v1",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        "vision_models": [],
        "image_models": [],
        "is_custom": False,
    },
    "qwen": {
        "id": "qwen",
        "name": "通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-turbo", "qwen-plus", "qwen-max", "qwen-long", "qwen-turbo-latest", "qwen-plus-latest", "qwen-max-latest"],
        "vision_models": ["qwen-vl-plus", "qwen-vl-max", "qwen-vl-max-latest"],
        "image_models": ["wanx-v1"],
        "is_custom": False,
    },
    "baidu": {
        "id": "baidu",
        "name": "百度文心",
        "base_url": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop",
        "models": ["ernie-4.0-turbo-8k", "ernie-4.0-8k", "ernie-3.5-8k", "ernie-speed-128k"],
        "vision_models": [],
        "image_models": [],
        "is_custom": False,
    },
}


def get_all_providers():
    """返回所有预设提供商（深拷贝）"""
    import copy
    return copy.deepcopy(PROVIDER_PRESETS)


def get_provider(preset_id: str):
    """获取单个预设提供商"""
    import copy
    p = PROVIDER_PRESETS.get(preset_id)
    return copy.deepcopy(p) if p else None


def model_supports_reasoning(provider_id: str, model_name: str) -> bool:
    """Best-effort capability check used when no dedicated reasoning role exists."""
    name = (model_name or "").lower()
    if provider_id == "openai":
        return name.startswith(("o1", "o3", "o4", "gpt-5"))
    hints = ("reasoner", "reasoning", "deepseek-r1", "qwq", "thinking")
    return any(hint in name for hint in hints)

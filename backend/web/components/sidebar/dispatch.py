from .models import (
    render_dashscope_model_options,
    render_deepseek_model_options,
    render_google_model_options,
    render_qianfan_model_options,
    render_siliconflow_model_options,
)
from .provider import (
    render_custom_model_options,
    render_openai_model_options,
    render_openrouter_model_options,
)


def render_model_options(llm_provider):
    if llm_provider == "dashscope":
        render_dashscope_model_options()
    elif llm_provider == "siliconflow":
        render_siliconflow_model_options()
    elif llm_provider == "deepseek":
        render_deepseek_model_options()
    elif llm_provider == "google":
        render_google_model_options()
    elif llm_provider == "qianfan":
        render_qianfan_model_options()
    elif llm_provider == "openai":
        render_openai_model_options()
    elif llm_provider == "custom_openai":
        render_custom_model_options()
    else:
        render_openrouter_model_options()

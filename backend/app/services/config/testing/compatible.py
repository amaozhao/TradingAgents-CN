from ..common import Optional, importlib, logger


class CompatibleApiTestMixin:
    def _test_openai_compatible_api(
        self,
        api_key: str,
        display_name: str,
        base_url: Optional[str] = None,
        provider_name: Optional[str] = None,
    ) -> dict:
        """测试 OpenAI 兼容 API（用于聚合渠道和自定义厂家）"""
        try:
            requests = importlib.import_module("requests")

            # 如果没有提供 base_url，使用默认值
            if not base_url:
                return {
                    "success": False,
                    "message": f"{display_name} 未配置 API 基础地址 (default_base_url)",
                }

            # 🔧 智能版本号处理：只有在没有版本号的情况下才添加 /v1
            # 避免对已有版本号的URL（如智谱AI的 /v4）重复添加 /v1
            re = importlib.import_module("re")
            logger.info(f"   [测试API] 原始 base_url: {base_url}")
            base_url = base_url.rstrip("/")
            logger.info(f"   [测试API] 去除斜杠后: {base_url}")

            if not re.search(r"/v\d+$", base_url):
                # URL末尾没有版本号，添加 /v1（OpenAI标准）
                base_url = base_url + "/v1"
                logger.info(f"   [测试API] 添加 /v1 版本号: {base_url}")
            else:
                # URL已包含版本号（如 /v4），不添加
                logger.info(f"   [测试API] 检测到已有版本号，保持原样: {base_url}")

            url = f"{base_url}/chat/completions"
            logger.info(f"   [测试API] 最终请求URL: {url}")

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }

            # 🔥 根据不同厂家选择合适的测试模型
            test_model = "gpt-3.5-turbo"  # 默认模型
            if provider_name == "siliconflow":
                # 硅基流动使用免费的 Qwen 模型进行测试
                test_model = "Qwen/Qwen2.5-7B-Instruct"
                logger.info(f"🔍 硅基流动使用测试模型: {test_model}")
            elif provider_name == "zhipu":
                # 智谱AI使用 glm-4 模型进行测试
                test_model = "glm-4"
                logger.info(f"🔍 智谱AI使用测试模型: {test_model}")

            # 使用一个通用的模型名称进行测试
            # 聚合渠道通常支持多种模型，这里使用 gpt-3.5-turbo 作为测试
            data = {
                "model": test_model,
                "messages": [
                    {
                        "role": "user",
                        "content": "Hello, please respond with 'OK' if you can read this.",
                    }
                ],
                "max_tokens": 200,  # 增加到200，给推理模型（如o1/gpt-5）足够空间
                "temperature": 0.1,
            }

            response = requests.post(url, json=data, headers=headers, timeout=15)

            if response.status_code == 200:
                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0]["message"]["content"]
                    if content and len(content.strip()) > 0:
                        return {
                            "success": True,
                            "message": f"{display_name} API连接测试成功",
                        }
                    else:
                        return {
                            "success": False,
                            "message": f"{display_name} API响应为空",
                        }
                else:
                    return {
                        "success": False,
                        "message": f"{display_name} API响应格式异常",
                    }
            elif response.status_code == 401:
                return {
                    "success": False,
                    "message": f"{display_name} API密钥无效或已过期",
                }
            elif response.status_code == 403:
                return {
                    "success": False,
                    "message": f"{display_name} API权限不足或配额已用完",
                }
            else:
                try:
                    error_detail = response.json()
                    error_msg = error_detail.get("error", {}).get(
                        "message", f"HTTP {response.status_code}"
                    )
                    logger.error(f"❌ [{display_name}] API测试失败")
                    logger.error(f"   请求URL: {url}")
                    logger.error(f"   状态码: {response.status_code}")
                    logger.error(f"   错误详情: {error_detail}")
                    return {
                        "success": False,
                        "message": f"{display_name} API测试失败: {error_msg}",
                    }
                except Exception:
                    logger.error(f"❌ [{display_name}] API测试失败")
                    logger.error(f"   请求URL: {url}")
                    logger.error(f"   状态码: {response.status_code}")
                    logger.error(f"   响应内容: {response.text[:500]}")
                    return {
                        "success": False,
                        "message": f"{display_name} API测试失败: HTTP {response.status_code}",
                    }

        except Exception as e:
            return {
                "success": False,
                "message": f"{display_name} API测试异常: {str(e)}",
            }

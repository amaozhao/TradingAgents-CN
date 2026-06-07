#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档一致性测试
Documentation Consistency Test

测试文档中的配置和说明是否一致
Test if configurations and descriptions in documentation are consistent
"""

import re
import sys

from support.path import REPO_ROOT

project_root = REPO_ROOT


def test_redis_commander_port_consistency():
    """
    测试 Redis Commander 端口配置的一致性
    Test Redis Commander port configuration consistency
    """
    print("🔍 测试 Redis Commander 端口配置一致性...")

    # 检查 backend/.env.example 文件
    env_example_path = project_root / "backend" / ".env.example"
    if env_example_path.exists():
        with open(env_example_path, "r", encoding="utf-8") as f:
            env_content = f.read()
            assert "Redis管理: http://localhost:8081" in env_content
            print(
                "✅ backend/.env.example 中 Redis Commander 主环境端口配置正确 (8081)"
            )

    compose_path = project_root / "deploy" / "docker" / "compose" / "docker-compose.yml"
    if compose_path.exists():
        with open(compose_path, "r", encoding="utf-8") as f:
            compose_content = f.read()
            assert '"8081:8081"' in compose_content
            assert "trading-agents-redis-commander" in compose_content
            print("✅ docker-compose.yml 中 Redis Commander 主环境端口配置正确 (8081)")

    # 检查 database_setup.md 文件
    db_setup_path = project_root / "docs" / "database_setup.md"
    if db_setup_path.exists():
        with open(db_setup_path, "r", encoding="utf-8") as f:
            db_content = f.read()
            # 应该包含 8082 端口
            assert "http://localhost:8082" in db_content
            assert "Redis Commander" in db_content
            print("✅ database_setup.md 中 Redis Commander 测试环境端口配置正确 (8082)")


def test_cli_command_format_consistency():
    """
    测试 CLI 命令格式的一致性
    Test CLI command format consistency
    """
    print("\n🔍 测试 CLI 命令格式一致性...")

    # 检查主要文档文件
    docs_to_check = ["README-CN.md", "docs/configuration/google-ai-setup.md"]

    for doc_file in docs_to_check:
        doc_path = project_root / doc_file
        if doc_path.exists():
            with open(doc_path, "r", encoding="utf-8") as f:
                content = f.read()

                # 检查是否使用了推荐的 python -m cli.main 格式
                old_format_count = len(re.findall(r"python cli/main\.py", content))
                len(re.findall(r"python -m cli\.main", content))

                assert old_format_count == 0
                print(f"✅ {doc_file} 中 CLI 命令格式正确")


def test_cli_smart_suggestions():
    """
    测试 CLI 智能建议功能
    Test CLI smart suggestions feature
    """
    print("\n🔍 测试 CLI 智能建议功能...")

    cli_imports_path = project_root / "backend" / "cli" / "main" / "imports.py"
    cli_models_path = project_root / "backend" / "cli" / "main" / "models.py"

    imports_content = cli_imports_path.read_text(encoding="utf-8")
    models_content = cli_models_path.read_text(encoding="utf-8")

    assert "get_close_matches" in imports_content
    assert "get_close_matches" in models_content
    assert "您是否想要使用以下命令之一" in models_content
    print("✅ CLI 智能建议功能已实现")


def test_documentation_structure():
    """
    测试文档结构的完整性
    Test documentation structure completeness
    """
    print("\n🔍 测试文档结构完整性...")

    # 检查关键文档是否存在
    key_docs = [
        "README.md",
        "docs/README.md",
        "docs/database_setup.md",
        "docs/overview/quick-start.md",
        "docs/configuration/data-directory-configuration.md",
    ]

    missing_docs = []
    for doc in key_docs:
        doc_path = project_root / doc
        if not doc_path.exists():
            missing_docs.append(doc)

    assert not missing_docs, f"缺少文档: {', '.join(missing_docs)}"
    print("✅ 所有关键文档都存在")


def main():
    """
    主测试函数
    Main test function
    """
    print("🚀 开始文档一致性测试...")
    print("=" * 50)

    tests = [
        test_redis_commander_port_consistency,
        test_cli_command_format_consistency,
        test_cli_smart_suggestions,
        test_documentation_structure,
    ]

    passed = 0
    total = len(tests)

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"❌ 测试 {test_func.__name__} 执行失败: {e}")

    print("\n" + "=" * 50)
    print(f"📊 测试结果: {passed}/{total} 通过")

    if passed == total:
        print("🎉 所有文档一致性测试通过！")
        return True
    else:
        print("⚠️ 部分测试未通过，请检查上述问题")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

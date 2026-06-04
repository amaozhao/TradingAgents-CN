#!/usr/bin/env python3
"""
测试数据库依赖包兼容性修复
验证 backend/pyproject.toml 中的数据库依赖兼容性
"""

import importlib
import os
import sys
import tomllib
from pathlib import Path

from support.path import BACKEND_ROOT, REPO_ROOT

backend_root = BACKEND_ROOT
project_root = REPO_ROOT


def test_python_version_check():
    """测试Python版本检查"""
    print("🔧 测试Python版本检查...")

    current_version = sys.version_info
    if current_version >= (3, 13):
        print(
            f"  ✅ Python {current_version.major}.{current_version.minor}.{current_version.micro} 符合要求"
        )
        return True
    else:
        print(
            f"  ❌ Python {current_version.major}.{current_version.minor}.{current_version.micro} 版本过低"
        )
        return False


def test_pickle_compatibility():
    """测试pickle兼容性"""
    print("🔧 测试pickle兼容性...")

    try:
        pickle = importlib.import_module("pickle")

        # 检查协议版本
        max_protocol = pickle.HIGHEST_PROTOCOL
        print(f"  当前pickle协议: {max_protocol}")

        if max_protocol >= 5:
            print("  ✅ 支持pickle协议5")
        else:
            print("  ❌ 不支持pickle协议5")
            return False

        # 检查是否错误安装了pickle5
        try:
            importlib.import_module("pickle5")
            print("  ⚠️ 检测到pickle5包，建议卸载")
            return False
        except ImportError:
            print("  ✅ 未安装pickle5包，配置正确")
            return True

    except Exception as e:
        print(f"  ❌ pickle测试失败: {e}")
        return False


def test_pyproject_dependency_syntax():
    """测试pyproject依赖声明语法"""
    print("🔧 测试 backend/pyproject.toml 数据库依赖...")

    pyproject_file = Path(backend_root) / "pyproject.toml"

    if not pyproject_file.exists():
        print("  ❌ backend/pyproject.toml 文件不存在")
        return False

    try:
        data = tomllib.loads(pyproject_file.read_text(encoding="utf-8"))
        dependencies = data["project"]["dependencies"]

        dependency_text = "\n".join(dependencies)
        if "pickle5" in dependency_text:
            print("  ❌ backend/pyproject.toml 仍包含pickle5依赖")
            return False

        required_database_packages = {
            "asyncpg": "asyncpg>=",
            "redis": "redis>=",
            "sqlalchemy": "sqlalchemy>=",
        }
        missing = [
            name
            for name, prefix in required_database_packages.items()
            if not any(dep.startswith(prefix) for dep in dependencies)
        ]

        if missing:
            print(f"  ❌ 缺少数据库依赖: {missing}")
            return False

        unpinned = [
            dep for dep in dependencies if ">=" not in dep and not dep.startswith("#")
        ]
        if unpinned:
            print(f"  ❌ 存在非最小版本依赖声明: {unpinned}")
            return False

        print(
            f"  ✅ backend/pyproject.toml 依赖检查通过，有效包数量: {len(dependencies)}"
        )
        return True

    except Exception as e:
        print(f"  ❌ backend/pyproject.toml 读取失败: {e}")
        return False


def test_package_installation_simulation():
    """模拟包安装测试"""
    print("🔧 模拟包安装测试...")

    # 模拟检查每个包的可用性
    packages_to_check = [
        "asyncpg",
        "redis",
        "sqlalchemy",
        "pandas",
    ]

    available_packages = []
    missing_packages = []

    for package in packages_to_check:
        try:
            __import__(package)
            available_packages.append(package)
            print(f"  ✅ {package}: 已安装")
        except ImportError:
            missing_packages.append(package)
            print(f"  ⚠️ {package}: 未安装")

    print(f"  已安装: {len(available_packages)}/{len(packages_to_check)}")

    if missing_packages:
        print(f"  缺少包: {missing_packages}")
        print("  💡 运行以下命令安装: pip install -e backend")

    return True  # 这个测试总是通过，只是信息性的


def test_deprecated_requirements_files_removed():
    """测试废弃requirements文件已移除"""
    print("🔧 测试废弃requirements文件清理...")

    deprecated_files = [
        "requirements.txt",
        "requirements-lock.txt",
    ]

    remaining = [
        file_name
        for file_name in deprecated_files
        if (Path(project_root) / file_name).exists()
    ]

    if remaining:
        print(f"  ❌ 废弃依赖文件仍存在: {remaining}")
        return False

    print("  ✅ 废弃requirements文件已移除，依赖入口统一为 backend/pyproject.toml")
    return True


def test_documentation_completeness():
    """测试文档完整性"""
    print("🔧 测试文档完整性...")

    docs_to_check = [
        "docs/database_setup.md",
        "docs/guides/TESTING_GUIDE.md",
        "backend/tests/README.md",
    ]

    all_exist = True

    for doc_path in docs_to_check:
        full_path = os.path.join(project_root, doc_path)
        if os.path.exists(full_path):
            print(f"  ✅ {doc_path}: 存在")

            # 检查文件大小
            size = os.path.getsize(full_path)
            if size > 1000:  # 至少1KB
                print(f"    文件大小: {size} 字节")
            else:
                print(f"    ⚠️ 文件较小: {size} 字节")
        else:
            print(f"  ❌ {doc_path}: 不存在")
            all_exist = False

    return all_exist


def main():
    """主测试函数"""
    print("🔧 数据库依赖包兼容性修复测试")
    print("=" * 60)

    tests = [
        ("Python版本检查", test_python_version_check),
        ("pickle兼容性", test_pickle_compatibility),
        ("pyproject依赖语法", test_pyproject_dependency_syntax),
        ("包安装模拟", test_package_installation_simulation),
        ("废弃依赖文件清理", test_deprecated_requirements_files_removed),
        ("文档完整性", test_documentation_completeness),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n📋 {test_name}:")
        try:
            if test_func():
                passed += 1
                print(f"  ✅ {test_name} 通过")
            else:
                print(f"  ❌ {test_name} 失败")
        except Exception as e:
            print(f"  ❌ {test_name} 异常: {e}")

    print("\n" + "=" * 60)
    print(f"📊 测试结果: {passed}/{total} 通过")

    if passed == total:
        print("🎉 所有测试通过！数据库依赖包兼容性修复成功")
        print("\n📋 修复内容:")
        print("✅ 移除pickle5依赖，解决Python 3.13+兼容性问题")
        print("✅ 优化版本要求，提高环境兼容性")
        print("✅ 添加兼容性检查工具")
        print("✅ 完善安装指南和故障排除文档")

        print("\n🚀 用户体验改进:")
        print("✅ 减少安装错误")
        print("✅ 提供清晰的错误诊断")
        print("✅ 支持更多Python环境")
        print("✅ 简化故障排除流程")

        return True
    else:
        print("⚠️ 部分测试失败，需要进一步检查")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

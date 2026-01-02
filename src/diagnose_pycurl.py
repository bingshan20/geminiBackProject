#!/usr/bin/env python3
import pycurl
import sys


def check_pycurl_features():
    """检查 pycurl 功能支持情况"""
    print("=== pycurl 功能诊断 ===")
    print(f"pycurl 版本: {pycurl.version}")

    # 检查重要属性
    attributes_to_check = [
        'XFERINFOFUNCTION',
        'PROGRESSFUNCTION',
        'NOPROGRESS',
        'URL',
        'POST',
        'WRITEDATA',
        'HTTPHEADER'
    ]

    print("\n支持的属性:")
    for attr in attributes_to_check:
        if hasattr(pycurl, attr):
            print(f"  ✓ {attr}")
        else:
            print(f"  ✗ {attr} (缺失)")

    # 尝试创建一个简单的 curl 对象测试基本功能
    try:
        c = pycurl.Curl()
        print("✓ 可以创建 Curl 对象")
        c.close()
    except Exception as e:
        print(f"✗ 创建 Curl 对象失败: {e}")

    return hasattr(pycurl, 'XFERINFOFUNCTION')


if __name__ == "__main__":
    if check_pycurl_features():
        print("\n✓ 当前 pycurl 支持 XFERINFOFUNCTION")
        sys.exit(0)
    else:
        print("\n✗ 当前 pycurl 不支持 XFERINFOFUNCTION，需要升级或修改代码")
        sys.exit(1)
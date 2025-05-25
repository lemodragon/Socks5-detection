#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SOCKS5批量检测工具启动脚本
此脚本会检查GeoIP数据库文件是否存在，并启动主程序
"""

import os
import sys
import shutil
import subprocess

def main():
    print("SOCKS5批量检测工具启动器")
    print("=" * 40)
    
    # 检查数据库文件
    db_file = "GeoLite2-City.mmdb"
    if not os.path.exists(db_file):
        print(f"GeoIP数据库文件不存在: {db_file}")
        
        # 尝试从备份目录复制
        backup_path = os.path.join("backup_data", db_file)
        if os.path.exists(backup_path):
            print(f"从备份中复制数据库文件...")
            shutil.copy2(backup_path, db_file)
            print(f"已复制数据库文件到当前目录")
        else:
            print("未找到备份数据库文件")
            print("请确保GeoLite2-City.mmdb文件位于与此脚本同一目录下")
            input("按回车键退出...")
            return
    
    print(f"数据库文件已确认: {os.path.abspath(db_file)}")
    
    # 启动主程序
    try:
        # 如果是打包后的EXE，直接运行check.py
        if os.path.exists("check.py"):
            print("启动主程序...")
            if sys.platform == "win32":
                subprocess.Popen(["python", "check.py"], shell=True)
            else:
                subprocess.Popen(["python3", "check.py"])
        # 如果是已打包的EXE，查找并运行
        else:
            exe_file = "SOCKS5批量检测工具.exe"
            if os.path.exists(exe_file):
                print(f"启动可执行文件: {exe_file}")
                subprocess.Popen([exe_file], shell=True)
            else:
                print(f"错误: 未找到可执行文件 {exe_file}")
                input("按回车键退出...")
                return
    except Exception as e:
        print(f"启动程序时出错: {e}")
        input("按回车键退出...")
        return
    
    print("程序已启动!")

if __name__ == "__main__":
    main() 
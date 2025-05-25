import os
import sys
import subprocess
import shutil
import time

def build_exe():
    """使用PyInstaller构建带图标的可执行文件"""
    print("开始构建SOCKS5批量检测工具...")
    
    # 检查图标文件是否存在
    icon_path = "app_icon.ico"
    if not os.path.exists(icon_path):
        print(f"警告: 图标文件 {icon_path} 不存在, 将使用默认图标。")
        print("请将您的图标文件以 'app_icon.ico' 命名放在此脚本同目录下。")
    else:
        print(f"找到图标文件: {os.path.abspath(icon_path)}")
    
    # 检查GeoIP数据库文件是否存在
    geoip_db = "GeoLite2-City.mmdb"
    if not os.path.exists(geoip_db):
        print(f"错误: GeoIP数据库文件 {geoip_db} 不存在!")
        print("请确保该文件位于脚本同目录下。")
        return
    
    # 清理旧的构建和dist目录
    for folder in ['build', 'dist']:
        if os.path.exists(folder):
            print(f"清理旧的{folder}目录...")
            try:
                shutil.rmtree(folder)
                time.sleep(1)  # 给系统一点时间完成删除
            except Exception as e:
                print(f"警告: 无法删除{folder}目录: {e}")
    
    # 直接执行pyinstaller命令，明确指定图标
    cmd = [
        "pyinstaller",
        f"--icon={icon_path}",
        "--name=SOCKS5批量检测工具", 
        "--windowed",          # 不显示控制台窗口
        "--onefile",           # 打包成单个文件
        "--clean",             # 清理临时文件
        "--noconfirm",         # 不询问确认
        "--add-data=GeoLite2-City.mmdb;.",  # 添加数据文件
        "--add-binary=app_icon.ico;.",      # 显式添加图标作为二进制资源
        "check.py"
    ]
    
    # 执行构建命令
    try:
        subprocess.run(cmd, check=True)
        print("\n构建成功! 可执行文件位于 dist 目录中。")
        exe_path = os.path.join("dist", "SOCKS5批量检测工具.exe")
        print(f"可执行文件: {exe_path}")
        
        # 确保图标文件被正确复制
        icon_dest = os.path.join("dist", "app_icon.ico")
        if not os.path.exists(icon_dest):
            print(f"复制图标文件到dist目录...")
            shutil.copy2(icon_path, icon_dest)
            
        # 确保数据库文件存在于dist目录中
        dist_db_path = os.path.join("dist", "GeoLite2-City.mmdb")
        if not os.path.exists(dist_db_path):
            print(f"\n注意: 数据库文件不在dist目录中，正在手动复制...")
            shutil.copy2(geoip_db, dist_db_path)
            print(f"已复制数据库文件到: {dist_db_path}")
        
        # 验证构建的EXE能否访问数据库文件
        print("\n打包内容验证:")
        if os.path.exists(exe_path):
            print(f"✓ EXE文件已创建: {exe_path}")
            file_size = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"  文件大小: {file_size:.2f} MB")
        else:
            print(f"✗ 未找到EXE文件: {exe_path}")
            
        # 提示用户可能需要手动复制数据库文件
        print("\n若程序无法显示国家和地区信息，请尝试以下步骤:")
        print("1. 确保程序运行目录中存在GeoLite2-City.mmdb文件")
        print("2. 已为您在backup_data目录中备份了数据库文件")
        print("3. 将backup_data目录中的GeoLite2-City.mmdb复制到与EXE同目录下")
        
        print("\n如果图标仍然不显示，请尝试以下步骤:")
        print("1. 确保app_icon.ico是标准ICO格式，包含多种尺寸 (16x16, 32x32, 48x48)")
        print("2. 使用专业工具(如IcoFX)创建图标文件")
        print("3. 运行dist目录中的.exe时，确保app_icon.ico在同一目录下")
    except subprocess.CalledProcessError as e:
        print(f"\n构建失败: {e}")
        print("请确保已安装PyInstaller: pip install pyinstaller")
    except FileNotFoundError:
        print("\n找不到PyInstaller。请先安装: pip install pyinstaller")

if __name__ == "__main__":
    build_exe()
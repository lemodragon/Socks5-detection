# Copyright 2024 SOCKS5 Batch Checker
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
SOCKS5 批量检测工具

一个功能强大的SOCKS5代理批量检测工具，支持协议检测、地理位置查询和结果导出。

主要功能：
- 批量检测SOCKS5代理可用性
- TCP/UDP协议支持检测
- 地理位置信息查询
- 延迟测试和状态显示
- 结果导出和复制功能
"""

import sys
import time
import requests
import geoip2.database
import concurrent.futures
import socket
import random
import struct
import csv
import os
import uuid
import platform
import threading
import json
from datetime import datetime

# 用于支持PyInstaller打包后的路径查找
def resource_path(relative_path):
    """获取资源的绝对路径，支持开发环境和PyInstaller打包后的环境，修复Windows中文路径问题"""
    try:
        # PyInstaller创建临时文件夹，将路径存储在_MEIPASS中
        # 由于_MEIPASS是PyInstaller特有的，IDE会报找不到这个属性的警告
        # 但这不影响实际运行
        base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    except Exception:
        # 不是通过PyInstaller运行时，使用当前目录
        base_path = os.path.abspath(".")
    
    path = os.path.join(base_path, relative_path)
    print(f"资源路径: {path} (存在: {os.path.exists(path)})")
    
    # 强化Windows中文路径编码处理
    if sys.platform == 'win32':
        try:
            # 确保路径是正确的Unicode字符串
            if isinstance(path, bytes):
                path = path.decode('utf-8')
            
            # 标准化路径
            path = os.path.normpath(path)
            
            # 确保路径是绝对路径
            if not os.path.isabs(path):
                path = os.path.abspath(path)
            
            print(f"Windows路径处理后: {path}")
            
        except Exception as e:
            print(f"路径编码处理警告: {e}")
    
    return path

# 图标加载和设置帮助函数
def load_app_icon():
    """加载应用图标并返回QIcon对象"""
    # 尝试多个位置加载图标
    icon_paths = [
        "app_icon.ico",  # 当前目录
        resource_path("app_icon.ico"),  # PyInstaller资源目录
        os.path.abspath("app_icon.ico"),  # 绝对路径
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_icon.ico")  # 脚本目录
    ]
    
    # 遍历所有可能的路径
    for path in set(icon_paths):  # 使用set去重
        if os.path.exists(path):
            print(f"尝试加载图标: {path}")
            try:
                icon = QIcon(path)
                if not icon.isNull():
                    print(f"成功加载图标: {path}")
                    return icon
            except Exception as e:
                print(f"加载图标失败: {e}")
                
    # 如果所有尝试都失败，返回空图标
    print("警告: 无法加载任何图标")
    return QIcon()

def set_dialog_icon(dialog):
    """为对话框设置图标"""
    if not hasattr(set_dialog_icon, "app_icon"):
        set_dialog_icon.app_icon = load_app_icon()
    
    if not set_dialog_icon.app_icon.isNull():
        dialog.setWindowIcon(set_dialog_icon.app_icon)

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QTextEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QLabel, QHBoxLayout, QProgressBar, QFrame,
    QFileDialog, QMenu, QAction
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QMutex, QSettings
from PyQt5.QtGui import QColor, QFont, QCursor, QIcon, QPixmap

class UmamiAnalytics:
    """Umami统计分析类 - 用于在桌面应用中实现类似Web分析的功能"""
    
    def __init__(self, umami_url="https://umami.lvdpub.com/script.js", website_id="b1fb94b8-e969-45e0-ba16-dc980fbf68aa"):
        # 请将 YOUR_ACTUAL_WEBSITE_ID 替换为您在Umami后台获取的实际website-id
        # 示例：website_id="2eb38a4d-3cd8-4b79-9cfb-9f95731dfc32"
        self.umami_url = umami_url
        self.website_id = website_id  # 从Umami后台获取的实际ID
        
        # 生成更持久的会话ID（基于时间和机器标识）
        import hashlib
        machine_id = f"{platform.node()}-{platform.system()}"
        current_hour = int(time.time() / 3600)  # 每小时更新一次会话
        session_string = f"{machine_id}-{current_hour}"
        self.session_id = hashlib.md5(session_string.encode()).hexdigest()
        self.user_id = hashlib.md5(machine_id.encode()).hexdigest()[:16]
        
        # 获取系统信息
        self.user_agent = self._get_user_agent()
        self.screen_resolution = self._get_screen_resolution()
        
        # 会话管理
        self.session_start_time = time.time()
        self.last_activity_time = time.time()
        self.is_active = True
        
        # 心跳定时器
        self.heartbeat_timer = None
        self.heartbeat_interval = 30  # 30秒心跳间隔
        
        # 可能的API端点列表（按优先级排序）
        # 根据script.js分析，您的服务器使用/api/send端点
        base_url = umami_url.replace('/script.js', '')
        self.possible_endpoints = [
            f"{base_url}/api/send",      # 您的服务器使用的端点（从script.js确认）
            f"{base_url}/api/collect",   # 旧版本端点
            f"{base_url}/api/track",     # 备选端点
            f"{base_url}/collect",       # 简化端点
        ]
        
        # 根据script.js分析，直接使用/api/send端点
        self.collect_url = f"{base_url}/api/send"
        
        # 获取本地IP地理位置信息
        self.user_location = self._get_user_location()
        
        # 打印配置信息用于调试
        print(f"Umami配置 - 使用API端点: {self.collect_url}, Website ID: {self.website_id}")
        print(f"用户位置: {self.user_location}")
    
    def _get_user_agent(self):
        """生成标准浏览器User-Agent"""
        system = platform.system()
        
        if system == "Windows":
            return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        elif system == "Darwin":
            return "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        else:
            return "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    def _get_screen_resolution(self):
        """获取屏幕分辨率"""
        try:
            from PyQt5.QtWidgets import QApplication, QDesktopWidget
            app = QApplication.instance()
            if app:
                desktop = QDesktopWidget()
                screen = desktop.screenGeometry()
                return f"{screen.width()}x{screen.height()}"
        except:
            pass
        return "1920x1080"  # 默认分辨率
    
    def _get_user_location(self):
        """获取用户地理位置信息"""
        try:
            # 首先尝试获取本地IP地址
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            
            # 如果是内网IP，尝试获取外网IP
            if local_ip.startswith(('192.168.', '10.', '172.')):
                try:
                    response = requests.get('https://api.ipify.org', timeout=3)
                    if response.status_code == 200:
                        external_ip = response.text.strip()
                        return self._get_ip_location(external_ip)
                except:
                    pass
            
            return self._get_ip_location(local_ip)
        except Exception as e:
            print(f"获取用户位置失败: {e}")
            return {'country': '未知', 'region': '未知', 'city': '未知'}
    
    def _get_ip_location(self, ip):
        """使用GeoIP数据库获取IP地理位置"""
        try:
            # 使用现有的GeoIP数据库
            db_path = resource_path('GeoLite2-City.mmdb')
            if os.path.exists(db_path):
                import geoip2.database
                import tempfile
                import shutil
                
                # Windows中文路径解决方案：复制数据库到临时英文路径
                if sys.platform == 'win32':
                    try:
                        # 创建临时文件（自动使用英文路径）
                        temp_fd, temp_path = tempfile.mkstemp(suffix='.mmdb', prefix='geoip_')
                        os.close(temp_fd)  # 关闭文件描述符
                        
                        # 复制数据库文件到临时路径
                        shutil.copy2(db_path, temp_path)
                        print(f"复制GeoIP数据库到临时路径: {temp_path}")
                        
                        # 使用临时路径加载数据库
                        with geoip2.database.Reader(temp_path) as reader:
                            response = reader.city(ip)
                            print(f"✅ GeoIP数据库加载成功（临时路径）: {temp_path}")
                            
                            result = {
                                'country': response.country.names.get('zh-CN', response.country.name or '未知'),
                                'region': response.subdivisions.most_specific.names.get('zh-CN', response.subdivisions.most_specific.name or '未知') if response.subdivisions else '未知',
                                'city': response.city.names.get('zh-CN', response.city.name or '未知')
                            }
                            
                            # 清理临时文件
                            try:
                                os.unlink(temp_path)
                                print(f"清理临时文件: {temp_path}")
                            except:
                                pass
                            
                            return result
                            
                    except Exception as temp_error:
                        print(f"临时文件方案失败: {temp_error}")
                        # 清理可能创建的临时文件
                        try:
                            if 'temp_path' in locals():
                                os.unlink(temp_path)
                        except:
                            pass
                
                # 非Windows系统或临时文件方案失败时，直接使用原路径
                try:
                    print(f"尝试直接加载GeoIP数据库: {db_path}")
                    with geoip2.database.Reader(db_path) as reader:
                        response = reader.city(ip)
                        print(f"✅ GeoIP数据库加载成功: {db_path}")
                        return {
                            'country': response.country.names.get('zh-CN', response.country.name or '未知'),
                            'region': response.subdivisions.most_specific.names.get('zh-CN', response.subdivisions.most_specific.name or '未知') if response.subdivisions else '未知',
                            'city': response.city.names.get('zh-CN', response.city.name or '未知')
                        }
                except Exception as direct_error:
                    print(f"直接加载失败: {direct_error}")
                
        except Exception as e:
            print(f"GeoIP查询失败: {e}")
            print(f"错误类型: {type(e)}")
        
        return {'country': '未知', 'region': '未知', 'city': '未知'}
    
    def _detect_api_endpoint(self):
        """检测正确的API端点"""
        print("正在检测Umami API端点...")
        
        for endpoint in self.possible_endpoints:
            try:
                # 发送一个简单的OPTIONS请求来检测端点是否存在
                print(f"测试端点: {endpoint}")
                response = requests.options(
                    endpoint,
                    headers={
                        "User-Agent": self.user_agent,
                        "Origin": "https://desktop-app",
                    },
                    timeout=3
                )
                
                # 如果返回200或405(Method Not Allowed，说明端点存在但不支持OPTIONS)
                if response.status_code in [200, 405]:
                    print(f"✅ 检测成功，使用端点: {endpoint}")
                    return endpoint
                    
            except Exception as e:
                print(f"❌ 端点 {endpoint} 测试失败: {e}")
                continue
        
        # 如果所有端点都失败，使用默认的/api/send
        default_endpoint = self.possible_endpoints[0]
        print(f"⚠️ 所有端点检测失败，使用默认端点: {default_endpoint}")
        return default_endpoint
    
    def _send_event(self, event_name, event_data=None, event_type="event"):
        """发送事件到Umami服务器 - 增强版本"""
        def send_request():
            try:
                # 更新最后活动时间
                self.last_activity_time = time.time()
                
                # 构建payload
                if event_type == "pageview":
                    # 页面访问事件 - 使用标准的页面访问格式
                    payload = {
                        "type": "event",
                        "payload": {
                            "website": self.website_id,
                            "hostname": "socks5-checker.desktop",
                            "url": f"/app/{event_name}",
                            "title": f"SOCKS5检测工具 - {event_name}",
                            "referrer": "",
                            "screen": self.screen_resolution
                        }
                    }
                    # 添加额外数据
                    if event_data:
                        payload["payload"]["data"] = event_data
                else:
                    # 自定义事件
                    payload = {
                        "type": "event",
                        "payload": {
                            "website": self.website_id,
                            "hostname": "socks5-checker.desktop",
                            "name": event_name
                        }
                    }
                    # 添加额外数据
                    if event_data:
                        payload["payload"]["data"] = event_data
                
                headers = {
                    "User-Agent": self.user_agent,
                    "Content-Type": "application/json"
                }
                
                # 发送请求
                response = requests.post(
                    self.collect_url,
                    json=payload,
                    headers=headers,
                    timeout=5
                )
                
                print(f"📊 发送{event_type}: {event_name} -> 状态码: {response.status_code}")
                if response.text:
                    # 检查是否是正常的JWT响应
                    if "cache" in response.text and "sessionId" in response.text:
                        print(f"✅ 事件发送成功！收到完整响应")
                    else:
                        print(f"📄 响应: {response.text}")
                    
            except Exception as e:
                print(f"❌ 发送事件失败: {e}")
        
        # 在新线程中发送
        thread = threading.Thread(target=send_request)
        thread.daemon = True
        thread.start()

    def _start_heartbeat(self):
        """启动心跳机制"""
        def heartbeat():
            if self.is_active:
                session_duration = int(time.time() - self.session_start_time)
                self.track_event("heartbeat", {
                    "session_duration": session_duration,
                    "last_activity": int(time.time() - self.last_activity_time)
                })
                # 重新设置定时器
                self.heartbeat_timer = threading.Timer(self.heartbeat_interval, heartbeat)
                self.heartbeat_timer.daemon = True
                self.heartbeat_timer.start()
        
        # 启动心跳
        self.heartbeat_timer = threading.Timer(self.heartbeat_interval, heartbeat)
        self.heartbeat_timer.daemon = True
        self.heartbeat_timer.start()
    
    def _stop_heartbeat(self):
        """停止心跳机制"""
        if self.heartbeat_timer:
            self.heartbeat_timer.cancel()
            self.heartbeat_timer = None

    def track_event(self, event_name, event_data=None):
        """追踪事件 - 简化版本"""
        self._send_event(event_name, event_data, "event")
    
    def track_page_view(self, page_name, page_data=None):
        """追踪页面访问"""
        self._send_event(page_name, page_data, "pageview")
    
    def track_app_start(self):
        """追踪应用启动"""
        # 发送页面访问事件（用于概览统计）
        self.track_page_view("应用启动", {
            "platform": platform.system(),
            "version": "1.0",
            "screen_resolution": self.screen_resolution,
            "location": self.user_location
        })
        
        # 发送应用启动事件（用于行为类别统计）
        self.track_event("app_start", {
            "platform": platform.system(),
            "version": "1.0",
            "screen_resolution": self.screen_resolution,
            "location": self.user_location,
            "session_id": self.session_id,
            "user_id": self.user_id
        })
        
        # 启动心跳机制
        self._start_heartbeat()
    
    def track_app_close(self):
        """追踪应用关闭"""
        session_duration = int(time.time() - self.session_start_time)
        
        # 发送页面访问事件
        self.track_page_view("应用关闭", {
            "session_duration": session_duration,
            "session_id": self.session_id
        })
        
        # 发送应用关闭事件
        self.track_event("app_close", {
            "session_duration": session_duration,
            "session_id": self.session_id
        })
        
        # 停止心跳
        self._stop_heartbeat()
        self.is_active = False
    
    def track_window_focus(self, focused=True):
        """追踪窗口焦点事件"""
        self.track_event("window_focus", {
            "focused": focused,
            "session_duration": int(time.time() - self.session_start_time)
        })
    
    def track_window_state(self, state):
        """追踪窗口状态变化"""
        self.track_event("window_state", {
            "state": state,  # "minimized", "normal", "maximized"
            "session_duration": int(time.time() - self.session_start_time)
        })
    
    def track_proxy_check(self, proxy_count):
        """追踪代理检测"""
        # 发送页面访问事件（用于概览统计）
        self.track_page_view("代理检测", {
            "proxy_count": proxy_count
        })
        
        # 发送代理检测事件（用于行为类别统计）
        self.track_event("proxy_check", {
            "proxy_count": proxy_count,
            "session_duration": int(time.time() - self.session_start_time)
        })
    
    def track_export(self, export_format, proxy_count):
        """追踪结果导出"""
        # 发送页面访问事件
        self.track_page_view("结果导出", {
            "format": export_format,
            "proxy_count": proxy_count
        })
        
        # 发送导出事件
        self.track_event("export_results", {
            "format": export_format,
            "proxy_count": proxy_count,
            "session_duration": int(time.time() - self.session_start_time)
        })
    
    def track_user_action(self, action_name, action_data=None):
        """追踪用户操作"""
        base_data = {
            "session_duration": int(time.time() - self.session_start_time),
            "session_id": self.session_id
        }
        
        if action_data:
            base_data.update(action_data)
        
        self.track_event(action_name, base_data)

class CheckerThread(QThread):
    result_signal = pyqtSignal(int, dict)
    progress_signal = pyqtSignal(int)
    
    def __init__(self, proxies):
        super().__init__()
        self.proxies = proxies
        self.mutex = QMutex()
        self.progress_count = 0
        self.reader = None
        self.temp_db_path = None  # 保存临时数据库路径
        
        # 使用与_get_ip_location相同的临时文件策略
        try:
            db_path = resource_path('GeoLite2-City.mmdb')
            if not os.path.exists(db_path):
                print(f"❌ GeoIP数据库文件不存在: {db_path}")
                return
            
            import geoip2.database
            import tempfile
            import shutil
            
            # Windows中文路径解决方案：复制数据库到临时英文路径
            if sys.platform == 'win32':
                try:
                    # 创建临时文件（自动使用英文路径）
                    temp_fd, temp_path = tempfile.mkstemp(suffix='.mmdb', prefix='geoip_checker_')
                    os.close(temp_fd)  # 关闭文件描述符
                    
                    # 复制数据库文件到临时路径
                    shutil.copy2(db_path, temp_path)
                    print(f"CheckerThread复制GeoIP数据库到临时路径: {temp_path}")
                    
                    # 使用临时路径加载数据库
                    self.reader = geoip2.database.Reader(temp_path)
                    self.temp_db_path = temp_path  # 保存临时路径，用于后续清理
                    print(f"✅ CheckerThread GeoIP数据库加载成功（临时路径）: {temp_path}")
                    return
                    
                except Exception as temp_error:
                    print(f"CheckerThread临时文件方案失败: {temp_error}")
                    # 清理可能创建的临时文件
                    try:
                        if 'temp_path' in locals():
                            os.unlink(temp_path)
                    except:
                        pass
            
            # 非Windows系统或临时文件方案失败时，直接使用原路径
            try:
                print(f"CheckerThread尝试直接加载GeoIP数据库: {db_path}")
                self.reader = geoip2.database.Reader(db_path)
                print(f"✅ CheckerThread GeoIP数据库加载成功: {db_path}")
            except Exception as direct_error:
                print(f"CheckerThread直接加载失败: {direct_error}")
                self.reader = None
            
        except Exception as e:
            print(f"CheckerThread GeoIP数据库初始化失败: {e}")
            self.reader = None
    
    def __del__(self):
        if hasattr(self, 'reader') and self.reader:
            self.reader.close()
        
        # 清理临时数据库文件
        if hasattr(self, 'temp_db_path') and self.temp_db_path:
            try:
                os.unlink(self.temp_db_path)
                print(f"清理CheckerThread临时数据库文件: {self.temp_db_path}")
            except:
                pass
    
    def get_location(self, ip):
        if not self.reader:
            return {'country': '未知', 'region': '未知'}
        try:
            response = self.reader.city(ip)
            country = response.country.names.get('zh-CN', response.country.name)
            region = response.subdivisions.most_specific.names.get('zh-CN', response.subdivisions.most_specific.name) if response.subdivisions else ''
            return {'country': country, 'region': region}
        except:
            return {'country': '未知', 'region': '未知'}
    
    def tcp_connect_test(self, ip, port, timeout=3):
        try:
            sock = socket.create_connection((ip, int(port)), timeout=timeout)
            sock.close()
            return True, ''
        except Exception as e:
            return False, str(e)
    
    def udp_connect_test(self, ip, port, user=None, pwd=None, timeout=3):
        """SOCKS5 UDP检测
        实现SOCKS5 UDP ASSOCIATE命令来检测UDP代理支持
        """
        try:
            # 建立TCP连接到SOCKS5代理
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((ip, int(port)))
            
            # SOCKS5握手
            # 发送认证方法选择
            if user and pwd:
                # 支持用户名/密码认证
                auth_methods = b'\x05\x02\x00\x02'  # 版本5, 2种方法, 无认证, 用户名/密码
            else:
                # 仅支持无认证
                auth_methods = b'\x05\x01\x00'  # 版本5, 1种方法, 无认证
            
            sock.send(auth_methods)
            response = sock.recv(2)
            
            if len(response) != 2 or response[0] != 0x05:
                sock.close()
                return False, "SOCKS5握手失败"
            
            # 处理认证
            if response[1] == 0x02:  # 需要用户名/密码认证
                if not user or not pwd:
                    sock.close()
                    return False, "需要用户名/密码认证"
                
                # 发送用户名/密码
                auth_request = bytes([0x01, len(user)]) + user.encode() + bytes([len(pwd)]) + pwd.encode()
                sock.send(auth_request)
                auth_response = sock.recv(2)
                
                if len(auth_response) != 2 or auth_response[1] != 0x00:
                    sock.close()
                    return False, "用户名/密码认证失败"
            elif response[1] == 0x00:  # 无认证
                pass
            else:
                sock.close()
                return False, f"不支持的认证方法: {response[1]}"
            
            # 发送UDP ASSOCIATE请求
            # 请求格式: VER CMD RSV ATYP DST.ADDR DST.PORT
            # VER=0x05, CMD=0x03(UDP ASSOCIATE), RSV=0x00, ATYP=0x01(IPv4)
            # DST.ADDR=0.0.0.0, DST.PORT=0 (表示任意地址和端口)
            udp_request = b'\x05\x03\x00\x01\x00\x00\x00\x00\x00\x00'
            sock.send(udp_request)
            
            # 接收响应
            response = sock.recv(10)  # 最小响应长度
            
            if len(response) < 6:
                sock.close()
                return False, "UDP ASSOCIATE响应太短"
            
            if response[0] != 0x05:
                sock.close()
                return False, "无效的SOCKS5响应"
            
            if response[1] == 0x00:  # 成功
                sock.close()
                return True, "UDP代理支持确认"
            else:
                sock.close()
                error_codes = {
                    0x01: "一般SOCKS服务器失败",
                    0x02: "连接不被允许",
                    0x03: "网络不可达",
                    0x04: "主机不可达",
                    0x05: "连接被拒绝",
                    0x06: "TTL过期",
                    0x07: "命令不支持",
                    0x08: "地址类型不支持"
                }
                error_msg = error_codes.get(response[1], f"未知错误代码: {response[1]}")
                return False, f"UDP ASSOCIATE失败: {error_msg}"
                
        except socket.timeout:
            return False, "UDP检测超时"
        except ConnectionRefusedError:
            return False, "连接被拒绝"
        except Exception as e:
            return False, f"UDP检测异常: {str(e)}"
    
    def test_proxy_connection(self, ip, port, user=None, pwd=None, max_retries=3):
        """测试代理连接，进行多次重试"""
        # 构建代理URL
        if user and pwd:
            proxy_url = f'socks5://{user}:{pwd}@{ip}:{port}'
        else:
            proxy_url = f'socks5://{ip}:{port}'
            
        proxies = {'http': proxy_url, 'https': proxy_url}
        
        # 更新测试端点，优先使用HTTP而非HTTPS
        test_endpoints = [
            {'url': 'http://ifconfig.me/ip', 'timeout': 5, 'type': 'text'},
            {'url': 'http://api.ipify.org', 'timeout': 5, 'type': 'text'},
            {'url': 'http://icanhazip.com', 'timeout': 5, 'type': 'text'},
            {'url': 'http://ident.me', 'timeout': 5, 'type': 'text'},
            {'url': 'http://ipinfo.io/ip', 'timeout': 5, 'type': 'text'}
        ]
        
        # 初始化TCP和UDP测试结果
        tcp_enabled = False
        udp_enabled = False
        tcp_error = ''
        udp_error = ''
        
        for attempt in range(max_retries):
            print(f"尝试检测代理 {ip}:{port} (第{attempt+1}次)")
            
            # 先进行TCP连接测试
            tcp_enabled, tcp_error = self.tcp_connect_test(ip, port)
            if not tcp_enabled:
                print(f"TCP连接失败: {tcp_error}")
                continue
            
            # 进行UDP连接测试
            udp_enabled, udp_error = self.udp_connect_test(ip, port, user, pwd)
            if udp_enabled:
                print(f"✅ UDP代理支持确认: {ip}:{port}")
            else:
                print(f"❌ UDP检测失败: {udp_error}")
                
            # 尝试每个测试端点
            for endpoint in test_endpoints:
                try:
                    start = time.time()
                    r = requests.get(endpoint['url'], proxies=proxies, timeout=endpoint['timeout'])
                    latency = int((time.time() - start) * 1000)
                    
                    if r.status_code == 200:
                        # 成功获取到IP
                        if endpoint['type'] == 'text':
                            # 纯文本类型，直接获取IP
                            ip_resp = r.text.strip()
                            # 获取地理位置信息
                            location = self.get_location(ip_resp)
                            country = location['country']
                            region = location['region']
                            
                            print(f"代理检测成功: {ip}:{port} -> {ip_resp}, 延迟: {latency}ms, TCP: {tcp_enabled}, UDP: {udp_enabled}")
                            return True, ip_resp, country, region, latency, tcp_enabled, udp_enabled
                    else:
                        print(f"请求失败，HTTP状态码: {r.status_code}")
                except Exception as e:
                    print(f"代理请求异常: {str(e)}")
        
        # 所有尝试均失败
        return False, '', '', '', 0, tcp_enabled, udp_enabled
    
    def check_socks5(self, proxy):
        # 先尝试用"|"分隔，再尝试用":"分隔
        if '|' in proxy:
            parts = proxy.strip().split('|')
        elif ':' in proxy:
            parts = proxy.strip().split(':')
        else:
            parts = []
            
        if len(parts) == 4:
            ip, port, user, pwd = parts
            # 多次尝试连接
            ok, ip_resp, country, region, latency, tcp_enabled, udp_enabled = self.test_proxy_connection(ip, port, user, pwd, max_retries=3)
        elif len(parts) == 2:
            ip, port = parts
            # 多次尝试连接
            ok, ip_resp, country, region, latency, tcp_enabled, udp_enabled = self.test_proxy_connection(ip, port, max_retries=3)
        else:
            return {'proxy': proxy, 'ok': False, 'ip': '', 'country': '未知', 'region': '未知', 'latency': '', 'tcp_enabled': False, 'udp_enabled': False, 'error': '格式错误'}
        
        if ok:
            return {
                'proxy': proxy, 
                'ok': True, 
                'ip': ip_resp, 
                'country': country, 
                'region': region, 
                'latency': latency,
                'tcp_enabled': tcp_enabled,
                'udp_enabled': udp_enabled,
                'error': ''
            }
        else:
            return {'proxy': proxy, 'ok': False, 'ip': '', 'country': '', 'region': '', 'latency': '', 'tcp_enabled': tcp_enabled, 'udp_enabled': udp_enabled, 'error': '连接失败'}
    
    def process_proxy(self, idx, proxy):
        """处理单个代理检测"""
        result = self.check_socks5(proxy)
        self.result_signal.emit(idx, result)
        
        # 安全地更新进度
        self.mutex.lock()
        self.progress_count += 1
        current = self.progress_count
        self.mutex.unlock()
        
        self.progress_signal.emit(current)
        return result
    
    def run(self):
        """使用线程池并发检测"""
        self.progress_count = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for idx, proxy in enumerate(self.proxies):
                futures.append(executor.submit(self.process_proxy, idx, proxy))
            
            # 等待所有任务完成
            concurrent.futures.wait(futures)

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SOCKS5 批量检测工具")
        
        # 初始化设置管理
        self.settings = QSettings('SOCKS5Checker', 'WindowSettings')
        
        # 初始化统计模块
        self.analytics = UmamiAnalytics()
        
        # 设置主窗口图标
        app_icon = load_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)
        
        # 窗口状态追踪
        self.last_window_state = None
        
        # 恢复窗口状态
        self.restore_window_state()
        
        self.setStyleSheet("""
            QWidget {
                background: #f7f7fa;
                font-family: 'Segoe UI', 'Microsoft YaHei', Arial, sans-serif;
                font-size: 16px;  /* 增大默认字体大小 */
            }
            QTableWidget {
                background: #fff;
                border-radius: 8px;
                border: 1px solid #e0e0e0;
                font-size: 16px;  /* 表格字体大小 */
            }
            QTextEdit, QLineEdit {
                background: #fff;
                border-radius: 8px;
                border: 1px solid #e0e0e0;
                padding: 6px;
                font-size: 16px;  /* 文本编辑框字体大小 */
            }
            QPushButton {
                background: #4f8cff;
                color: #fff;
                border-radius: 8px;
                padding: 10px 20px;  /* 增大按钮内边距 */
                font-weight: bold;
                font-size: 16px;  /* 按钮字体大小 */
                border: none;
            }
            QPushButton:hover {
                background: #3a78e7;
            }
            QPushButton:pressed {
                background: #2a62c9;
            }
            QPushButton:disabled {
                background: #b0c4de;
                color: #eee;
            }
            QHeaderView::section {
                background: #f0f4fa;
                font-weight: bold;
                border: none;
                border-bottom: 1px solid #e0e0e0;
                font-size: 16px;  /* 表头字体大小 */
                padding: 5px;  /* 增加表头内边距 */
            }
            QProgressBar {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                text-align: center;
                font-size: 14px;  /* 进度条文本大小 */
            }
            QProgressBar::chunk {
                background-color: #4f8cff;
                border-radius: 3px;
            }
            QLabel#disclaimer {
                color: #666;
                font-size: 14px;  /* 声明文本大小 */
            }
            QLabel#contact {
                color: #4f8cff;
                font-size: 14px;  /* 联系方式文本大小 */
                text-decoration: underline;
            }
            QLabel#tutorial {
                color: #ff0000;
                font-size: 14px;  /* 教程链接文本大小 */
                text-decoration: underline;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)  # 增大布局元素间距

        title = QLabel("SOCKS5 批量检测工具")
        title.setFont(QFont("Segoe UI", 24, QFont.Bold))  # 增大标题字体
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        input_frame = QFrame()
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)

        self.textEdit = QTextEdit()
        self.textEdit.setPlaceholderText("每行一个 SOCKS5 节点（ip|端口|用户名|密码 或 ip:端口:用户名:密码）")
        input_layout.addWidget(self.textEdit)

        btn_layout = QVBoxLayout()
        self.button = QPushButton("开始检测")
        self.clear_btn = QPushButton("清空输入")
        btn_layout.addWidget(self.button)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addStretch()
        input_layout.addLayout(btn_layout)
        layout.addWidget(input_frame)

        # 进度条和进度标签的容器
        progress_frame = QFrame()
        progress_layout = QHBoxLayout(progress_frame)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        
        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.setFixedHeight(30)  # 增大进度条高度
        progress_layout.addWidget(self.progress)
        
        self.progress_label = QLabel("0/0")
        self.progress_label.setMinimumWidth(80)  # 增大标签宽度
        self.progress_label.setFont(QFont("Segoe UI", 16))  # 设置更大的字体
        progress_layout.addWidget(self.progress_label)
        
        layout.addWidget(progress_frame)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(['代理', '可用', 'TCP', 'UDP', '出口IP', '国家', '地区', '延迟(ms)'])
        # 配置表格头部和动态列宽
        self.setup_table_headers()
        # 设置表格文字居中
        self.table.setStyleSheet(self.table.styleSheet() + """
            QTableWidget::item {
                text-align: center;
                padding: 5px;
            }
        """)
        
        # 设置代理列的省略显示模式
        self.table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        layout.addWidget(self.table)

        # 按钮区域
        btn_frame = QFrame()
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        
        self.export_btn = QPushButton("导出可用代理")
        self.export_btn.clicked.connect(self.export_working_proxies)
        btn_layout.addWidget(self.export_btn)
        
        self.clear_result_btn = QPushButton("清空结果")
        self.clear_result_btn.clicked.connect(self.clear_results)
        btn_layout.addWidget(self.clear_result_btn)
        
        layout.addWidget(btn_frame, alignment=Qt.AlignmentFlag.AlignRight)
        
        # 添加作者声明和联系信息
        disclaimer_frame = QFrame()
        disclaimer_layout = QVBoxLayout(disclaimer_frame)
        disclaimer_layout.setContentsMargins(0, 5, 0, 0)
        
        # 声明信息
        disclaimer_label = QLabel("本工具不存储和上传任何用户内容，请放心使用。(👉ﾟヮﾟ)👉 <span style='color: #ff0000; text-decoration: underline;'><a href='https://mp.weixin.qq.com/s/j_9Mk-sr5v5uty6ieyYGsQ' style='color: #ff0000;'>教程</a></span>")
        disclaimer_label.setObjectName("disclaimer")
        disclaimer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        disclaimer_label.setOpenExternalLinks(False)  # 禁用自动打开链接
        disclaimer_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        disclaimer_label.linkActivated.connect(self.on_tutorial_link_clicked)  # 连接点击事件
        disclaimer_layout.addWidget(disclaimer_label)
        
        # 联系方式
        contact_label = QLabel("<a href='https://demo.lvdpub.com'>联系作者: https://demo.lvdpub.com</a>")
        contact_label.setObjectName("contact")
        contact_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        contact_label.setOpenExternalLinks(False)  # 禁用自动打开链接
        contact_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        contact_label.linkActivated.connect(self.on_contact_link_clicked)  # 连接点击事件
        disclaimer_layout.addWidget(contact_label)
        
        layout.addWidget(disclaimer_frame)

        self.button.clicked.connect(self.start_check)
        self.clear_btn.clicked.connect(self.clear_input)
        
        # 保存代理总数和结果
        self.total_proxies = 0
        self.results = []
        
        # 发送应用启动统计事件
        self.analytics.track_app_start()
        
        # 连接窗口事件
        self.installEventFilter(self)
    
    def restore_window_state(self):
        """恢复窗口状态"""
        # 恢复窗口几何信息
        geometry = self.settings.value('geometry')
        if geometry:
            self.restoreGeometry(geometry)
        else:
            # 默认窗口大小
            self.resize(1200, 700)
    
    def save_window_state(self):
        """保存窗口状态"""
        # 保存窗口几何信息
        self.settings.setValue('geometry', self.saveGeometry())
        
        # 保存表格列宽状态
        header = self.table.horizontalHeader()
        if header:
            column_widths = []
            for i in range(self.table.columnCount()):
                column_widths.append(header.sectionSize(i))
            self.settings.setValue('column_widths', column_widths)
    
    def setup_table_headers(self):
        """设置表格头部和动态列宽"""
        header = self.table.horizontalHeader()
        if header is not None:
            # 设置列宽调整模式
            header.setSectionResizeMode(0, QHeaderView.Stretch)      # 代理列 - 自动拉伸
            header.setSectionResizeMode(1, QHeaderView.Fixed)        # 可用列 - 固定宽度
            header.setSectionResizeMode(2, QHeaderView.Fixed)        # TCP列 - 固定宽度
            header.setSectionResizeMode(3, QHeaderView.Fixed)        # UDP列 - 固定宽度
            header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # 出口IP列 - 内容自适应
            header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # 国家列 - 内容自适应
            header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # 地区列 - 内容自适应
            header.setSectionResizeMode(7, QHeaderView.Fixed)        # 延迟列 - 固定宽度
            
            # 设置固定列的宽度
            header.resizeSection(1, 80)   # 可用列宽
            header.resizeSection(2, 80)   # TCP列宽
            header.resizeSection(3, 80)   # UDP列宽
            header.resizeSection(7, 100)  # 延迟列宽
            
            # 设置最小列宽
            header.setMinimumSectionSize(80)
            
            # 尝试恢复保存的列宽
            saved_widths = self.settings.value('column_widths')
            if saved_widths and len(saved_widths) == self.table.columnCount():
                try:
                    for i, width in enumerate(saved_widths):
                        if i not in [0, 4, 5, 6]:  # 跳过拉伸列和内容自适应列
                            # 确保宽度是整数类型
                            width_int = int(width) if isinstance(width, str) else width
                            if width_int > 0:  # 验证宽度有效性
                                header.resizeSection(i, width_int)
                except (ValueError, TypeError) as e:
                    print(f"恢复列宽时出错: {e}")
                    # 如果恢复失败，使用默认宽度
        
        self.table.setAlternatingRowColors(True)
        # 设置表格的上下文菜单策略
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        # 设置表格双击事件
        self.table.cellDoubleClicked.connect(self.copy_cell_content)
        # 设置更大的行高
        vertical_header = self.table.verticalHeader()
        if vertical_header:
            vertical_header.setDefaultSectionSize(40)
    
    def eventFilter(self, obj, event):
        """事件过滤器，用于捕获窗口事件"""
        if obj == self:
            if event.type() == event.WindowStateChange:
                # 窗口状态变化
                if self.isMinimized():
                    self.analytics.track_window_state("minimized")
                elif self.isMaximized():
                    self.analytics.track_window_state("maximized")
                else:
                    self.analytics.track_window_state("normal")
            elif event.type() == event.FocusIn:
                # 窗口获得焦点
                self.analytics.track_window_focus(True)
            elif event.type() == event.FocusOut:
                # 窗口失去焦点
                self.analytics.track_window_focus(False)
        
        return super().eventFilter(obj, event)
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 保存窗口状态
        self.save_window_state()
        
        # 发送应用关闭统计
        self.analytics.track_app_close()
        
        # 等待一小段时间确保统计数据发送完成
        import time
        time.sleep(0.5)
        
        event.accept()
    
    def clear_input(self):
        """清空输入框"""
        self.textEdit.clear()

    def start_check(self):
        proxies = [line.strip() for line in self.textEdit.toPlainText().split('\n') if line.strip()]
        if not proxies:
            self.show_message_box("提示", "请输入至少一个代理！", QMessageBox.Warning)
            return
        
        self.total_proxies = len(proxies)
        
        # 发送代理检测统计事件
        self.analytics.track_proxy_check(self.total_proxies)
        self.table.setRowCount(self.total_proxies)
        for i, proxy in enumerate(proxies):
            # 设置代理列，添加工具提示
            proxy_item = QTableWidgetItem(proxy)
            proxy_item.setToolTip(proxy)  # 工具提示显示完整代理信息
            self.table.setItem(i, 0, proxy_item)
            self.table.setItem(i, 1, QTableWidgetItem("检测中..."))
            self.table.setItem(i, 2, QTableWidgetItem("检测中..."))
            self.table.setItem(i, 3, QTableWidgetItem("检测中..."))
            for j in range(4, 8):
                self.table.setItem(i, j, QTableWidgetItem(""))

        self.button.setEnabled(False)
        self.progress.setMaximum(self.total_proxies)
        self.progress.setValue(0)
        self.progress_label.setText(f"0/{self.total_proxies}")
        
        # 清空之前的结果
        self.results = []
        
        self.checker = CheckerThread(proxies)
        self.checker.result_signal.connect(self.update_result)
        self.checker.progress_signal.connect(self.update_progress)
        self.checker.finished.connect(self.check_finished)
        self.checker.start()

    def update_progress(self, value):
        """更新进度显示"""
        self.progress.setValue(value)
        self.progress_label.setText(f"{value}/{self.total_proxies}")

    def update_result(self, idx, res):
        # 保存结果
        self.results.append(res)
        
        # 更新代理列 - 添加省略显示和工具提示
        proxy_item = QTableWidgetItem(res['proxy'])
        proxy_item.setToolTip(res['proxy'])  # 工具提示显示完整代理信息
        # 存储完整文本用于复制，显示时会自动省略
        self.table.setItem(idx, 0, proxy_item)
        
        ok_item = QTableWidgetItem("✅" if res['ok'] else "❌")
        ok_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if res['ok']:
            ok_item.setBackground(QColor("#d4f7d4"))
        else:
            ok_item.setBackground(QColor("#ffd6d6"))
        self.table.setItem(idx, 1, ok_item)
        
        # 更新TCP状态
        tcp_item = QTableWidgetItem("✅" if res['tcp_enabled'] else "❌")
        tcp_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if res['tcp_enabled']:
            tcp_item.setBackground(QColor("#d4f7d4"))
        else:
            tcp_item.setBackground(QColor("#ffd6d6"))
        self.table.setItem(idx, 2, tcp_item)
        
        # 更新UDP状态
        udp_item = QTableWidgetItem("✅" if res['udp_enabled'] else "❌")
        udp_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if res['udp_enabled']:
            udp_item.setBackground(QColor("#d4f7d4"))
        else:
            udp_item.setBackground(QColor("#ffd6d6"))
        self.table.setItem(idx, 3, udp_item)
        
        # 更新其他字段
        self.table.setItem(idx, 4, QTableWidgetItem(res['ip']))
        self.table.setItem(idx, 5, QTableWidgetItem(res['country']))
        self.table.setItem(idx, 6, QTableWidgetItem(res['region']))
        latency_item = QTableWidgetItem(str(res['latency']))
        if res['ok'] and res['latency']:
            latency = int(res['latency'])
            if latency < 300:
                latency_item.setBackground(QColor("#d4f7d4"))
            elif latency < 1000:
                latency_item.setBackground(QColor("#fff7d6"))
            else:
                latency_item.setBackground(QColor("#ffd6d6"))
        self.table.setItem(idx, 7, latency_item)

    def check_finished(self):
        self.button.setEnabled(True)
        self.show_message_box("检测完成", "所有代理检测完成！", QMessageBox.Information)

    def clear_results(self):
        self.table.setRowCount(0)
        self.progress.setValue(0)
        self.progress_label.setText("0/0")
        self.total_proxies = 0
        self.results = []

    def copy_cell_content(self, row, column):
        """双击单元格时复制内容到剪贴板"""
        item = self.table.item(row, column)
        if item and item.text():
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(item.text())
                # 显示复制成功的状态提示
                self.show_message_box("复制成功", f"已复制 '{item.text()}' 到剪贴板！")
    
    def show_context_menu(self, position):
        """显示上下文菜单"""
        menu = QMenu(self)
        
        # 获取当前选中的单元格
        indexes = self.table.selectedIndexes()
        if len(indexes) > 0:
            copy_action = QAction("复制单元格内容", self)
            copy_action.triggered.connect(self.copy_selected_cells)
            menu.addAction(copy_action)
            
            # 如果是代理列，添加复制代理的选项
            if indexes[0].column() == 0:
                copy_proxy_action = QAction("复制代理", self)
                copy_proxy_action.triggered.connect(self.copy_selected_proxy)
                menu.addAction(copy_proxy_action)
        
        menu.exec_(QCursor.pos())
    
    def copy_selected_cells(self):
        """复制选中单元格的内容"""
        indexes = self.table.selectedIndexes()
        if len(indexes) > 0:
            text = ""
            for index in indexes:
                item = self.table.item(index.row(), index.column())
                if item and item.text():
                    text += item.text() + "\t"
            
            if text:
                clipboard = QApplication.clipboard()
                if clipboard:
                    clipboard.setText(text.strip())
                    self.show_message_box("复制成功", "已复制选中内容到剪贴板！")
    
    def copy_selected_proxy(self):
        """复制选中的代理"""
        indexes = self.table.selectedIndexes()
        selected_rows = set()
        for index in indexes:
            selected_rows.add(index.row())
        
        if selected_rows:
            text = ""
            for row in selected_rows:
                proxy_item = self.table.item(row, 0)
                if proxy_item and proxy_item.text():
                    text += proxy_item.text() + "\n"
            
            if text:
                clipboard = QApplication.clipboard()
                if clipboard:
                    clipboard.setText(text.strip())
                    self.show_message_box("复制成功", "已复制代理到剪贴板！")
    
    def export_working_proxies(self):
        """导出可用的代理"""
        if not self.results:
            self.show_message_box("提示", "没有可导出的代理检测结果！", QMessageBox.Warning)
            return
        
        # 筛选可用的代理
        working_proxies = [res for res in self.results if res['ok']]
        if not working_proxies:
            self.show_message_box("提示", "没有可用的代理！", QMessageBox.Warning)
            return
        
        # 获取导出文件路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        file_dialog = QFileDialog(self)
        set_dialog_icon(file_dialog)  # 设置文件对话框图标
        file_path, _ = file_dialog.getSaveFileName(
            self, "导出可用代理", 
            os.path.join(current_dir, "working_proxies.csv"),
            "CSV文件 (*.csv);;文本文件 (*.txt);;所有文件 (*.*)"
        )
        
        if not file_path:
            return
        
        try:
            # 根据文件扩展名选择导出格式
            if file_path.lower().endswith('.csv'):
                # CSV格式导出，使用UTF-8-BOM编码解决Excel中文乱码问题
                with open(file_path, 'wb') as f:
                    # 写入UTF-8 BOM，使Excel正确识别UTF-8编码
                    f.write(b'\xef\xbb\xbf')
                
                with open(file_path, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    # 写入表头
                    writer.writerow(['代理', '出口IP', '国家', '地区', '延迟(ms)', 'TCP', 'UDP'])
                    # 写入数据
                    for proxy in working_proxies:
                        writer.writerow([
                            proxy['proxy'],
                            proxy['ip'],
                            proxy['country'],
                            proxy['region'],
                            proxy['latency'],
                            '是' if proxy['tcp_enabled'] else '否',
                            '是' if proxy['udp_enabled'] else '否'
                        ])
            else:
                # 文本格式导出，每行一个代理
                with open(file_path, 'w', encoding='utf-8') as f:
                    for proxy in working_proxies:
                        f.write(f"{proxy['proxy']}\n")
            
            # 发送导出结果统计事件
            export_format = "csv" if file_path.lower().endswith('.csv') else "txt"
            self.analytics.track_export(export_format, len(working_proxies))
            
            self.show_message_box("导出成功", f"成功导出 {len(working_proxies)} 个可用代理到 {file_path}")
        except Exception as e:
            error_msg = QMessageBox(QMessageBox.Critical, "导出失败", f"导出失败: {str(e)}", QMessageBox.Ok, self)
            set_dialog_icon(error_msg)  # 使用助手函数设置图标
            error_msg.exec_()

    def show_message_box(self, title, text, icon_type=QMessageBox.Information):
        """显示统一样式的消息框"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(text)
        msg_box.setIcon(icon_type)
        
        # 设置消息框图标
        set_dialog_icon(msg_box)
            
        # 使用更大的字体
        font = msg_box.font()
        font.setPointSize(12)
        msg_box.setFont(font)
        
        msg_box.exec_()

    def on_tutorial_link_clicked(self, url):
        """处理教程链接点击"""
        # 发送链接点击统计
        self.analytics.track_event("教程", {
            "url": url
        })
        
        # 打开链接
        import webbrowser
        webbrowser.open(url)
    
    def on_contact_link_clicked(self, url):
        """处理联系作者链接点击"""
        # 发送链接点击统计
        self.analytics.track_event("联系作者", {
            "url": url
        })
        
        # 打开链接
        import webbrowser
        webbrowser.open(url)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # 设置应用程序级图标
    app_icon = load_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)
    
    # Windows平台特定设置
    if sys.platform == 'win32':
        try:
            import ctypes
            myappid = 'lvdpub.socks5checker.1.0'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            print("已设置Windows应用程序ID")
        except Exception as e:
            print(f"设置Windows应用程序ID失败: {e}")
    
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
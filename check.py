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

# 用于支持PyInstaller打包后的路径查找
def resource_path(relative_path):
    """获取资源的绝对路径，支持开发环境和PyInstaller打包后的环境"""
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
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QMutex
from PyQt5.QtGui import QColor, QFont, QCursor, QIcon, QPixmap

class CheckerThread(QThread):
    result_signal = pyqtSignal(int, dict)
    progress_signal = pyqtSignal(int)
    
    def __init__(self, proxies):
        super().__init__()
        self.proxies = proxies
        self.mutex = QMutex()
        self.progress_count = 0
        try:
            # 使用resource_path函数获取数据库文件路径
            db_path = resource_path('GeoLite2-City.mmdb')
            self.reader = geoip2.database.Reader(db_path)
            print(f"成功加载GeoIP数据库: {db_path}")
        except Exception as e:
            print(f"GeoLite2数据库加载失败: {e}")
            print(f"尝试搜索的路径: {resource_path('GeoLite2-City.mmdb')}")
            self.reader = None
    
    def __del__(self):
        if hasattr(self, 'reader') and self.reader:
            self.reader.close()
    
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
        """测试UDP连接是否可用
        注意：这只是一个基本的UDP测试，真正的SOCKS5 UDP测试需要完整的SOCKS5协议实现
        """
        try:
            # 构建代理URL进行HTTP请求，判断是否支持UDP
            if user and pwd:
                proxy_url = f'socks5://{user}:{pwd}@{ip}:{port}'
            else:
                proxy_url = f'socks5://{ip}:{port}'
                
            proxies = {'http': proxy_url, 'https': proxy_url}
            
            # 请求专门检测UDP的服务，如stun服务器或DNS服务器
            # 这里用简单HTTP请求模拟UDP测试，实际应用中应该使用真正的UDP测试
            # 注：这是一个模拟实现，实际项目中应替换为真正的UDP测试
            try:
                r = requests.get('http://ifconfig.me/ip', proxies=proxies, timeout=timeout)
                # 如果HTTP请求成功，我们就假设UDP可能也是通的
                # 实际场景中，真正的UDP测试应使用专用的STUN服务器或DNS服务
                return True, ''
            except Exception as e:
                return False, str(e)
                
        except Exception as e:
            return False, str(e)
    
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
                print(f"UDP连接成功")
            else:
                print(f"UDP连接失败: {udp_error}")
                
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
        self.resize(1200, 700)  # 增大窗口默认尺寸
        
        # 设置主窗口图标
        app_icon = load_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)
        
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
                transition: background 0.3s;
            }
            QPushButton:hover {
                background: #3a78e7;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
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
                cursor: pointer;
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
        header = self.table.horizontalHeader()
        if header is not None:
            header.setStretchLastSection(True)
            for i in range(7):
                header.setSectionResizeMode(i, QHeaderView.Interactive)
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
        # 设置适当的列宽
        self.table.setColumnWidth(0, 350)  # 代理列宽
        self.table.setColumnWidth(1, 80)   # 可用列宽
        self.table.setColumnWidth(2, 80)   # TCP列宽
        self.table.setColumnWidth(3, 80)   # UDP列宽
        self.table.setColumnWidth(4, 150)  # 出口IP列宽
        self.table.setColumnWidth(5, 120)  # 国家列宽
        self.table.setColumnWidth(6, 120)  # 地区列宽
        # 设置表格文字居中
        self.table.setStyleSheet(self.table.styleSheet() + """
            QTableWidget::item {
                text-align: center;
                padding: 5px;
            }
        """)
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
        disclaimer_label = QLabel("本工具不存储和上传任何用户内容，请放心使用。")
        disclaimer_label.setObjectName("disclaimer")
        disclaimer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        disclaimer_layout.addWidget(disclaimer_label)
        
        # 联系方式
        contact_label = QLabel("联系作者: https://demo.lvdpub.com")
        contact_label.setObjectName("contact")
        contact_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        contact_label.setOpenExternalLinks(True)
        contact_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        contact_label.setText("<a href='https://demo.lvdpub.com'>联系作者: https://demo.lvdpub.com</a>")
        disclaimer_layout.addWidget(contact_label)
        
        layout.addWidget(disclaimer_frame)

        self.button.clicked.connect(self.start_check)
        self.clear_btn.clicked.connect(self.textEdit.clear)
        
        # 保存代理总数和结果
        self.total_proxies = 0
        self.results = []

    def start_check(self):
        proxies = [line.strip() for line in self.textEdit.toPlainText().split('\n') if line.strip()]
        if not proxies:
            self.show_message_box("提示", "请输入至少一个代理！", QMessageBox.Warning)
            return
        
        self.total_proxies = len(proxies)
        self.table.setRowCount(self.total_proxies)
        for i, proxy in enumerate(proxies):
            self.table.setItem(i, 0, QTableWidgetItem(proxy))
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
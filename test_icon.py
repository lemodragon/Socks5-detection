#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
图标加载测试工具
用于验证ICO文件是否能被正确加载为Qt图标
"""

import os
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QPushButton, QFileDialog
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtCore import Qt

class IconTester(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("图标测试工具")
        self.setGeometry(100, 100, 500, 300)
        
        # 创建中央控件和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 创建选择文件的按钮
        self.select_btn = QPushButton("选择图标文件...")
        self.select_btn.clicked.connect(self.select_icon)
        layout.addWidget(self.select_btn)
        
        # 测试当前目录的app_icon.ico
        self.test_default_btn = QPushButton("测试当前目录的app_icon.ico")
        self.test_default_btn.clicked.connect(self.test_default_icon)
        layout.addWidget(self.test_default_btn)
        
        # 显示状态的标签
        self.status_label = QLabel("请选择图标文件或测试默认图标")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        # 显示图标的标签
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.icon_label)
        
        # 显示图标信息的标签
        self.info_label = QLabel()
        self.info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.info_label)
    
    def select_icon(self):
        """选择图标文件并测试"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择图标文件", "", "图标文件 (*.ico);;所有文件 (*.*)"
        )
        if file_path:
            self.test_icon(file_path)
    
    def test_default_icon(self):
        """测试当前目录的app_icon.ico文件"""
        default_icon = "app_icon.ico"
        if os.path.exists(default_icon):
            self.test_icon(default_icon)
        else:
            self.status_label.setText(f"错误: 找不到文件 {default_icon}")
            self.icon_label.clear()
            self.info_label.setText("")
    
    def test_icon(self, icon_path):
        """测试指定的图标文件"""
        self.status_label.setText(f"测试图标: {icon_path}")
        
        # 尝试加载为QIcon
        icon = QIcon(icon_path)
        if icon.isNull():
            self.status_label.setText(f"错误: 无法加载图标 {icon_path}")
            self.icon_label.clear()
            self.info_label.setText("")
            return
        
        # 显示图标信息
        sizes = icon.availableSizes()
        size_info = []
        for size in sizes:
            size_info.append(f"{size.width()}x{size.height()}")
        
        if size_info:
            self.info_label.setText(f"图标尺寸: {', '.join(size_info)}")
        else:
            self.info_label.setText("警告: 图标没有可用尺寸")
        
        # 显示图标
        self.setWindowIcon(icon)
        
        # 尝试加载为QPixmap并显示
        try:
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                # 调整大小保持纵横比
                pixmap = pixmap.scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.icon_label.setPixmap(pixmap)
                self.status_label.setText(f"成功加载图标: {icon_path}")
            else:
                self.status_label.setText(f"警告: 无法将图标加载为像素图 {icon_path}")
                self.icon_label.clear()
        except Exception as e:
            self.status_label.setText(f"错误: {str(e)}")
            self.icon_label.clear()

def main():
    app = QApplication(sys.argv)
    tester = IconTester()
    tester.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 
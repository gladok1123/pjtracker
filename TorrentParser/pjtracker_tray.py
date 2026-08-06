import sys
import os
import threading
import webbrowser
import requests
import time
import json
import re
import socket
import base64
from cryptography.fernet import Fernet
from flask import Flask, render_template, request, jsonify, send_from_directory
from PyQt5.QtWidgets import (QApplication, QSystemTrayIcon, QMenu, QAction, 
                             QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QMessageBox, QComboBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

# ==================== ЖЁСТКАЯ ПРОВЕРКА НА ДУБЛИ ====================
def is_already_running():
    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.settimeout(0.3)
        result = test_socket.connect_ex(('127.0.0.1', 5001))
        test_socket.close()
        return result == 0
    except:
        return False

if is_already_running():
    print("PJTracker уже запущен! Открываю сайт...")
    webbrowser.open("http://localhost:5000")
    sys.exit(0)

# ==================== ШИФРОВАНИЕ ====================

KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'secret.key')

def generate_key():
    key = Fernet.generate_key()
    with open(KEY_FILE, 'wb') as key_file:
        key_file.write(key)
    return key

def load_key():
    if not os.path.exists(KEY_FILE):
        return generate_key()
    with open(KEY_FILE, 'rb') as key_file:
        return key_file.read()

def encrypt_data(data):
    key = load_key()
    f = Fernet(key)
    return f.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data):
    try:
        key = load_key()
        f = Fernet(key)
        return f.decrypt(encrypted_data.encode()).decode()
    except:
        return None

# ==================== КОНФИГУРАЦИЯ ====================

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')

def load_config():
    default_config = {
        'jackett_url': 'http://127.0.0.1:9117',
        'jackett_api_key_encrypted': encrypt_data('hp1e62d0b9zbuy11535wam7expgpx23r'),
        'torrserver_url': 'http://127.0.0.1:8090'
    }
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                for key in default_config:
                    if key not in config:
                        config[key] = default_config[key]
                return config
        except:
            return default_config
    return default_config

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return True
    except:
        return False

CONFIG = load_config()
JACKETT_URL = CONFIG['jackett_url']
JACKETT_API_KEY = decrypt_data(CONFIG['jackett_api_key_encrypted'])
TORRSERVER_URL = CONFIG['torrserver_url']

if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
ICON_DIR = os.path.join(BASE_DIR, 'icons')

app_flask = Flask(__name__, template_folder=TEMPLATE_DIR)

def parse_size(size_str):
    if not size_str:
        return 0
    if isinstance(size_str, (int, float)):
        return size_str
    size_str = str(size_str).strip()
    match = re.search(r'([\d.]+)\s*([ГМК]?Б)', size_str, re.IGNORECASE)
    if not match:
        match = re.search(r'([\d.]+)\s*(GB|MB|KB|TB)', size_str, re.IGNORECASE)
        if not match:
            return 0
    num = float(match.group(1))
    unit = match.group(2).upper()
    if unit in ['ГБ', 'GB']:
        return num * 1024 * 1024 * 1024
    elif unit in ['МБ', 'MB']:
        return num * 1024 * 1024
    elif unit in ['КБ', 'KB']:
        return num * 1024
    elif unit in ['ТБ', 'TB']:
        return num * 1024 * 1024 * 1024 * 1024
    return num

def search_jackett(query=None, category=None, tracker=None):
    global JACKETT_URL, JACKETT_API_KEY
    params = {
        'apikey': JACKETT_API_KEY,
        'Query': query if query else '',
    }
    if category:
        params['Category'] = category
    if tracker and tracker != 'all':
        params['Tracker'] = tracker
    
    try:
        response = requests.get(f"{JACKETT_URL}/api/v2.0/indexers/all/results", params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except:
        return None

def clean_title(title):
    if not title:
        return ""
    return ' '.join(title.strip().split())

def get_available_trackers():
    global JACKETT_URL, JACKETT_API_KEY
    try:
        response = requests.get(f"{JACKETT_URL}/api/v2.0/indexers", params={'apikey': JACKETT_API_KEY}, timeout=10)
        response.raise_for_status()
        data = response.json()
        trackers = []
        if 'Indexers' in data:
            for idx in data['Indexers']:
                if 'ID' in idx and 'Title' in idx:
                    trackers.append({
                        'id': idx['ID'],
                        'title': idx['Title']
                    })
        return trackers
    except:
        return []

def get_torrserver_status():
    try:
        response = requests.get(f"{TORRSERVER_URL}/api/v1/version", timeout=5)
        return response.status_code == 200
    except:
        return False

# ==================== МАРШРУТЫ FLASK ====================

@app_flask.before_request
def restrict_local():
    if request.remote_addr != '127.0.0.1':
        return "Access denied. Local only.", 403

@app_flask.route('/')
def index():
    query = request.args.get('q', '')
    category = request.args.get('category', '')
    tracker = request.args.get('tracker', 'all')
    priority = request.args.get('priority', '')  # <--- ДОБАВЛЕНО
    
    results = []
    error = None
    
    if query:
        data = search_jackett(query, category, tracker)
        if data is None:
            error = "Не удалось подключиться к Jackett. Проверьте настройки в меню трея."
        elif 'Results' in data:
            results = data['Results']
            for result in results:
                if 'Title' in result:
                    result['Title'] = clean_title(result['Title'])
    
    available_trackers = get_available_trackers()
    
    return render_template(
        'index.html',
        results=results,
        query=query,
        category=category,
        tracker=tracker,
        priority=priority,          # <--- ПЕРЕДАЁМ В ШАБЛОН
        error=error,
        trackers=available_trackers
    )

@app_flask.route('/category/<category_id>')
def category_view(category_id):
    categories = {
        '1000': 'Movies',
        '2000': 'TV Series', 
        '3000': 'Music',
        '4000': 'Games',
        '4050': 'Games PC',
        '5000': 'Software'
    }
    category_name = categories.get(category_id, 'Category')
    
    tracker = request.args.get('tracker', 'all')
    priority = request.args.get('priority', '')  # <--- ДОБАВЛЕНО
    data = search_jackett(query='', category=category_id, tracker=tracker)
    
    results = []
    error = None
    if data is None:
        error = "Не удалось подключиться к Jackett"
    elif 'Results' in data:
        results = data['Results']
        for result in results:
            if 'Title' in result:
                result['Title'] = clean_title(result['Title'])
    
    available_trackers = get_available_trackers()
    
    return render_template(
        'index.html',
        results=results,
        query='',
        category=category_id,
        tracker=tracker,
        priority=priority,          # <--- ПЕРЕДАЁМ В ШАБЛОН
        error=error,
        category_name=category_name,
        trackers=available_trackers
    )

@app_flask.route('/icons/<path:filename>')
def serve_icon(filename):
    return send_from_directory(ICON_DIR, filename)

@app_flask.route('/api/status')
def api_status():
    jackett_status = False
    try:
        response = requests.get(f"{JACKETT_URL}/api/v2.0/indexers", params={'apikey': JACKETT_API_KEY}, timeout=5)
        if response.status_code == 200:
            jackett_status = True
    except:
        pass
    
    torrserver_status = get_torrserver_status()
    
    return jsonify({
        'jackett': jackett_status,
        'jackett_url': JACKETT_URL,
        'torrserver': torrserver_status,
        'torrserver_url': TORRSERVER_URL
    })

def run_flask():
    app_flask.run(port=5000, host='127.0.0.1', debug=False, use_reloader=False)

# ==================== UI НАСТРОЕК (ТОЛЬКО URL И API) ====================

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки PJTracker")
        self.setFixedSize(520, 300)
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        
        layout = QVBoxLayout()
        
        # Jackett URL
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("Jackett URL:"))
        self.jackett_url_input = QLineEdit()
        self.jackett_url_input.setText(JACKETT_URL)
        self.jackett_url_input.setPlaceholderText("http://127.0.0.1:9117")
        url_layout.addWidget(self.jackett_url_input)
        layout.addLayout(url_layout)
        
        # Jackett API Key
        api_layout = QHBoxLayout()
        api_layout.addWidget(QLabel("Jackett API Key:"))
        self.jackett_api_input = QLineEdit()
        self.jackett_api_input.setText(JACKETT_API_KEY)
        self.jackett_api_input.setPlaceholderText("Введите API ключ Jackett")
        api_layout.addWidget(self.jackett_api_input)
        layout.addLayout(api_layout)
        
        # TorrServer URL
        torr_layout = QHBoxLayout()
        torr_layout.addWidget(QLabel("TorrServer URL:"))
        self.torrserver_url_input = QLineEdit()
        self.torrserver_url_input.setText(TORRSERVER_URL)
        self.torrserver_url_input.setPlaceholderText("http://127.0.0.1:8090")
        torr_layout.addWidget(self.torrserver_url_input)
        layout.addLayout(torr_layout)
        
        # Кнопки
        btn_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("Сохранить")
        self.save_btn.clicked.connect(self.save_settings)
        self.save_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 6px 20px; border-radius: 6px;")
        btn_layout.addWidget(self.save_btn)
        
        self.test_btn = QPushButton("Проверить Jackett")
        self.test_btn.clicked.connect(self.test_connection)
        self.test_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 6px 20px; border-radius: 6px;")
        btn_layout.addWidget(self.test_btn)
        
        self.close_btn = QPushButton("Закрыть")
        self.close_btn.clicked.connect(self.close)
        self.close_btn.setStyleSheet("background-color: #f44336; color: white; padding: 6px 20px; border-radius: 6px;")
        btn_layout.addWidget(self.close_btn)
        
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
    
    def save_settings(self):
        global JACKETT_URL, JACKETT_API_KEY, TORRSERVER_URL
        
        new_config = {
            'jackett_url': self.jackett_url_input.text().strip(),
            'jackett_api_key_encrypted': encrypt_data(self.jackett_api_input.text().strip()),
            'torrserver_url': self.torrserver_url_input.text().strip()
        }
        
        if save_config(new_config):
            JACKETT_URL = new_config['jackett_url']
            JACKETT_API_KEY = self.jackett_api_input.text().strip()
            TORRSERVER_URL = new_config['torrserver_url']
            QMessageBox.information(self, "Успешно", "Настройки сохранены!\nAPI-ключ зашифрован.")
            self.close()
        else:
            QMessageBox.critical(self, "Ошибка", "Не удалось сохранить настройки.")
    
    def test_connection(self):
        test_url = self.jackett_url_input.text().strip()
        test_api = self.jackett_api_input.text().strip()
        
        try:
            response = requests.get(f"{test_url}/api/v2.0/indexers", params={'apikey': test_api}, timeout=5)
            if response.status_code == 200:
                QMessageBox.information(self, "Успешно", "✅ Подключение к Jackett успешно!")
            else:
                QMessageBox.warning(self, "Ошибка", f"⚠️ Jackett ответил с ошибкой: HTTP {response.status_code}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"❌ Не удалось подключиться к Jackett:\n{str(e)}")

# ==================== ТРЕЙ ====================

class TrayApp(QSystemTrayIcon):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        icon_path = os.path.join(ICON_DIR, 'favicon.ico')
        if os.path.exists(icon_path):
            self.setIcon(QIcon(icon_path))
        else:
            self.setIcon(QIcon.fromTheme('applications-internet'))
        
        self.setToolTip("PJTracker - Сервер запущен")
        
        self.menu = QMenu()
        
        self.open_action = QAction("Открыть веб-сервис", self)
        self.open_action.triggered.connect(self.open_web)
        self.menu.addAction(self.open_action)
        
        self.settings_action = QAction("Настройки", self)
        self.settings_action.triggered.connect(self.open_settings)
        self.menu.addAction(self.settings_action)
        
        self.status_action = QAction("Проверить статус", self)
        self.status_action.triggered.connect(self.check_status)
        self.menu.addAction(self.status_action)
        
        self.menu.addSeparator()
        
        self.exit_action = QAction("Выход", self)
        self.exit_action.triggered.connect(self.exit_app)
        self.menu.addAction(self.exit_action)
        
        self.setContextMenu(self.menu)
        self.show()

    def open_web(self):
        webbrowser.open("http://localhost:5000")
    
    def open_settings(self):
        dialog = SettingsDialog()
        dialog.exec_()

    def check_status(self):
        try:
            response = requests.get("http://localhost:5000/api/status", timeout=5)
            if response.status_code == 200:
                data = response.json()
                msg = "🔍 Статус сервисов:\n\n"
                msg += f"📡 Jackett: {'✅' if data['jackett'] else '❌'} ({data['jackett_url']})\n"
                msg += f"📡 TorrServer: {'✅' if data['torrserver'] else '❌'} ({data['torrserver_url']})"
                QMessageBox.information(None, "Статус", msg)
            else:
                QMessageBox.warning(None, "Ошибка", "Не удалось получить статус")
        except:
            QMessageBox.critical(None, "Ошибка", "❌ Не удалось подключиться к локальному серверу")

    def exit_app(self):
        self.hide()
        QApplication.quit()
        sys.exit(0)

# ==================== ЗАПУСК ====================

def main():
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    time.sleep(1)
    
    webbrowser.open("http://localhost:5000")
    
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    tray = TrayApp()
    
    print("="*50)
    print("PJTracker запущен в трее!")
    print("="*50)
    print(f"Jackett URL: {JACKETT_URL}")
    print(f"TorrServer URL: {TORRSERVER_URL}")
    print("\nСайт открыт в браузере: http://localhost:5000")
    print("="*50)
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
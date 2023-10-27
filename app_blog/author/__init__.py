from flask import Flask, request, render_template, jsonify
import sqlite3
import base64
import socket
from flask_socketio import SocketIO
import json
from datetime import datetime
from cachetools import LRUCache

def get_local_ip_address():
    try:
        # 创建一个套接字对象
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # 连接到外部 IP 地址，但并不需要进行实际通信
        s.connect(("8.8.8.8", 80))

        # 获取本地 IP 地址
        local_ip_address = s.getsockname()[0]

        # 关闭套接字
        s.close()

        return local_ip_address
    except Exception as e:
        print("Error:", str(e))
        return None

ServerIP = get_local_ip_address()
# print(ServerIP)
ServerPort = '5000'
dbPath = 'car_info.db'

app = Flask(__name__, template_folder='../templates/author')
app.config['SERVER_NAME'] = ServerIP + ':' + ServerPort  # Replace with your actual domain and port
socketio = SocketIO(app)

# SQLite数据库初始化
def init_db():
    conn = sqlite3.connect(dbPath)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS CarInfo (
            ID INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            CarType TEXT,
            LicensePlate TEXT,
            Time TEXT,
            Location TEXT,
            Image TEXT,
            Status TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# 分页设置
PER_PAGE = 5

# 将日期时间字符串从datetime-local格式转换为数据库格式
def convert_to_db_datetime(datetime_str):
    # 解析输入日期时间字符串的格式
    print(datetime_str)
    datetime_format_input = "%Y-%m-%dT%H:%M%S"  # datetime-local格式
    input_datetime = datetime.strptime(datetime_str, datetime_format_input)
    print(input_datetime)

    # 将datetime-local格式的日期时间转换为数据库格式
    db_datetime_format = "%Y-%m-%d %H:%M:%S"
    db_datetime = input_datetime.strftime(db_datetime_format)
    print(db_datetime)

    return db_datetime

# 創建一個緩存，設置最大緩存大小
# cache = LRUCache(maxsize=128)

total_pages = 1  # 設置默認值

# 在主页的路由中处理搜索请求
@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)

    # 嘗試從緩存中獲取數據
    # car_data = cache.get(page)

    # if car_data is None:
    # 如果緩存中不存在數據，則執行新的查詢並存儲到緩存
    license_plate = request.args.get('license_plate')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    status = request.args.get('status_type')

    conn = sqlite3.connect(dbPath)
    cursor = conn.cursor()

    # 构建SQL查询语句，考虑搜索条件
    count_query = 'SELECT * FROM CarInfo WHERE 1 = 1'  # WHERE 1=1 用于构建动态查询条件

    if license_plate:
        count_query += f" AND LicensePlate LIKE '%{license_plate}%'"

    if start_date and end_date:
        # start_date_db = convert_to_db_datetime(start_date)
        # end_date_db = convert_to_db_datetime(end_date)
        count_query += f" AND Time >= '{start_date}' AND Time <= '{end_date}'"
    elif start_date:
        # start_date_db = convert_to_db_datetime(start_date)
        count_query += f" AND Time >= '{start_date}'"
    elif end_date:
        # end_date_db = convert_to_db_datetime(end_date)
        count_query += f" AND Time <= '{end_date}'"

    if status:
        count_query += f" AND Status LIKE '%{status}%'"

    cursor.execute(count_query)
    total_count = len(cursor.fetchall())  # 總記錄數

    # 计算总页数
    # if total_count > 0:
    global total_pages
    total_pages = total_count // PER_PAGE  # 使用整除運算符 '//' 得到整數部分
    if total_count % PER_PAGE != 0:
        total_pages += 1

    count_query += f' ORDER BY ID DESC LIMIT {PER_PAGE} OFFSET {(page - 1) * PER_PAGE}'

    cursor.execute(count_query)
    car_data = cursor.fetchall()
    conn.close()

    # 存儲檢索到的數據到緩存
    # cache[page] = car_data
    
    return render_template('index.html', car_data=car_data, page=page, PER_PAGE=PER_PAGE, ServerIP=ServerIP, ServerPort=ServerPort, total_pages=total_pages)


# 在WebSocket连接时，将初始数据发送给客户端
@socketio.on('connect')
def handle_connect():
    conn = sqlite3.connect(dbPath)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM CarInfo ORDER BY ID DESC LIMIT ?', (PER_PAGE,))
    car_data = cursor.fetchall()
    conn.close()
    socketio.emit('initial_data', json.dumps(car_data))  # 使用 json.dumps 将数据转换为 JSON 格式
    # 使用 jsonify 将数据转换为 JSON 格式
    return jsonify(car_data)

# 辨識車輛並將資訊存入資料庫，与之前的代码一致
@app.route('/recognize', methods=['POST'])
def recognize():
    car_type = request.form.get('car_type')
    license_plate = request.form.get('license_plate')
    time = request.form.get('time')
    location = request.form.get('location')
    photo_data = request.form.get('photo_data')
    status_data = request.form.get('status_data')

    conn = sqlite3.connect(dbPath)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO CarInfo (CarType, LicensePlate, Time, Location, Image, Status) VALUES (?, ?, ?, ?, ?, ?)",
                   (car_type, license_plate, time, location, photo_data, status_data))
    conn.commit()
    conn.close()
    socketio.emit('update_data', 'Data has been updated')  # 发送WebSocket消息以通知客户端数据已更新
    return "Success"

# 在后端创建一个接受 HTTP 请求的路由，用于接收 prepage 变量
@app.route('/updatePrepage', methods=['POST'])
def update_prepage():
    prepage = request.form.get('prepage')  # 从请求中获取 prepage 变量
    # print('prepage 變量的值:', prepage)

    # 在这里你可以对 prepage 变量执行任何需要的后端操作

    return "Success"  # 返回一个响应给前端

@app.route('/updateTable', methods=['get'])
def updateTable():
    page = request.args.get('page', 1, type=int)
    conn = sqlite3.connect(dbPath)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM CarInfo ORDER BY ID DESC LIMIT ? OFFSET ?',
                   (PER_PAGE, (page - 1) * PER_PAGE))
    car_data = cursor.fetchall()
    conn.close()
    socketio.emit('update_data_information', json.dumps(car_data))  # 使用 json.dumps 将数据转换为 JSON 格式
    return jsonify(car_data)
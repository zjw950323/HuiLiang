import os
import uuid
import datetime
import mysql.connector
import requests
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from io import BytesIO
from PIL import Image

app = Flask(__name__)

# 设置上传文件的存储路径
# UPLOAD_FOLDER = '/usr/share/nginx/html/pic/'
UPLOAD_FOLDER = '/Users/muse/uploads/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Let's API 密钥
LET_API_KEY = 'sk-uwKTwkUwX6gZLjuDCh2862qEfDEJ7tSkDUGTPLOqQGHNs5Fz'
LET_API_URL = 'https://api.aigc369.com/v1/images/generations'

# 数据库配置
DB_HOST = '121.40.43.143'
DB_USER = 'root'
DB_PASSWORD = '*Huiliang2024'
DB_NAME = 'HuiLiang'
DB_TABLE = 'ai_pic'


# 获取数据库连接
def get_db_connection():
    conn = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
    return conn


# 判断文件扩展名是否合法
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# 使用 Let's API 生成图片
def generate_image(description):
    headers = {
        'Authorization': f'Bearer {LET_API_KEY}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    data = {
        'prompt': description,
        'n': 1,
        'size': '1024x1024',
        'model': 'dall-e-3'
    }

    response = requests.post(LET_API_URL, headers=headers, json=data)

    if response.status_code == 200:
        response_json = response.json()
        return response_json['data'][0]['url']
    else:
        raise Exception(f"Failed to generate image. Status code: {response.status_code}, Response: {response.text}")


# 上传图片到服务器的指定目录并获取存储地址
def upload_image(image_url, description):
    image_response = requests.get(image_url)
    image = Image.open(BytesIO(image_response.content))

    # 获取文件扩展名
    file_extension = image_url.split('.')[-1]

    # 将图片保存到服务器指定目录
    filename = f"{description[:10]}_{str(uuid.uuid4().hex[:6])}.png"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    image.save(filepath)

    # 返回保存的文件路径
    return filepath


# 将图片信息存储到数据库
def save_image_to_db(description, image_name, image_path):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "INSERT INTO {} (description, image_name, image_path) VALUES (%s, %s, %s)".format(DB_TABLE)
    cursor.execute(query, (description, image_name, image_path))
    conn.commit()
    conn.close()


# 对外提供的接口，查询数据库是否已有匹配的图片
@app.route('/get_image', methods=['GET'])
def get_image_by_description():
    description = request.args.get('description', '')

    if not description:
        return jsonify({"error": "No description provided"}), 400

    # 查询数据库是否已有匹配的图片
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query = "SELECT image_name, image_path FROM {} WHERE description LIKE %s".format(DB_TABLE)
    cursor.execute(query, ('%' + description + '%',))
    result = cursor.fetchall()
    conn.close()

    if result:
        return jsonify({"code": 200, "data": result}), 200
    else:
        # 如果没有匹配的图片，调用 Let's API 生成一张图片
        image_url = generate_image(description)
        image_name = f"{description[:10]}_generated.png"  # 生成一个图片名称
        image_path = upload_image(image_url, description)

        # 将生成的图片信息保存到数据库
        save_image_to_db(description, image_name, image_path)

        return jsonify(
            {"code": 200, "data": [{"image_name": image_name, "image_path": image_path}]}
        ), 200


if __name__ == '__main__':
    # 创建上传目录（如果不存在）
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    app.run(host='0.0.0.0', port=5000)
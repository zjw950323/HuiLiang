import datetime
import os
import random
import string
from io import BytesIO

import mysql.connector
import requests
from PIL import Image
from flask import Flask, request, jsonify

app = Flask(__name__)

# 设置上传文件的存储路径
UPLOAD_FOLDER = '/usr/share/nginx/html/pic/'
# UPLOAD_FOLDER = '/Users/muse/uploads/'
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
DB_VERSION_TABLE = 'version_control'  # 假设你有一个保存版本信息的表


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
def generate_image(model, size, description):
    headers = {
        'Authorization': f'Bearer {LET_API_KEY}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    print(model)
    print(size)
    print(description)
    data = {
        'prompt': description,
        'n': 1,
        'size': size,
        'model': model
    }

    response = requests.post(LET_API_URL, headers=headers, json=data)

    if response.status_code == 200:
        response_json = response.json()
        print(response_json['data'][0]['url'])
        return response_json['data'][0]['url']
    else:
        raise Exception(f"Failed to generate image. Status code: {response.status_code}, Response: {response.text}")


# 上传图片到服务器的指定目录并获取存储地址
def upload_image(image_url, image_name):
    image_response = requests.get(image_url)
    image = Image.open(BytesIO(image_response.content))

    filename = image_name
    filepath = os.path.join(UPLOAD_FOLDER, filename)

    # 保存图片
    image.save(filepath)

    # 返回保存的文件路径
    return filepath


# 将图片信息存储到数据库
def save_image_to_db(image_name, image_path,  image_model, image_size, image_description):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = f"INSERT INTO {DB_TABLE} (image_name, image_path,  image_model, image_size, image_description) VALUES (%s, %s, %s, %s, %s)"
    cursor.execute(query, (image_name, image_path,  image_model, image_size, image_description))
    conn.commit()
    conn.close()


# 查询最新版本信息的接口
@app.route('/get_latest_version', methods=['GET'])
def get_latest_version():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 获取最新的版本信息
    query = f"SELECT version_number, update_description, create_time, update_time, is_force_update, update_url FROM {DB_VERSION_TABLE} ORDER BY update_time DESC LIMIT 1"
    cursor.execute(query)
    result = cursor.fetchone()
    conn.close()

    if result:
        return jsonify({
            "code": 200,
            "data": result
        }), 200
    else:
        return jsonify({
            "code": 404,
            "message": "No version information found."
        }), 404


# 对外提供的接口，查询数据库是否已有匹配的图片
@app.route('/get_image', methods=['GET'])
def get_image_by_description():
    model = request.args.get('model', '')
    size = request.args.get('size', '')
    description = request.args.get('description', '')

    if not model:
        return jsonify({"error": "No model provided"}), 400
    if not size:
        return jsonify({"error": "No size provided"}), 400
    if not description:
        return jsonify({"error": "No description provided"}), 400

    # 将description分成多个字节，每个字节前加上"%"符号
    encoded_description = '%'.join(description)
    # 查询数据库是否已有匹配的图片
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query = "SELECT image_name, image_model, image_size, image_description FROM {} WHERE image_description LIKE %s AND image_model = %s AND image_size = %s".format(
        DB_TABLE)
    cursor.execute(query, ('%' + encoded_description + '%', model, size))
    result = cursor.fetchall()
    conn.close()

    if result:
        return jsonify({"code": 200, "data": result}), 200
    else:
        # 如果没有匹配的图片，调用 Let's API 生成一张图片
        image_url = generate_image(model, size, description)
        image_name = f"image_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{''.join(random.choices(string.digits + string.ascii_lowercase, k=10))}.png"
        image_path = upload_image(image_url, image_name)

        # 将生成的图片信息保存到数据库
        save_image_to_db(image_name, image_path, model, size, description)

        return jsonify({"code": 200, "data": [
            {"image_name": image_name, "image_model": model,
             "image_size": size, "image_description": description}]}), 200


# 对外提供的接口，调用 Let's API 生成一张图片
@app.route('/get_image_generate', methods=['GET'])
def get_image_generate():
    model = request.args.get('model', '')
    size = request.args.get('size', '')
    description = request.args.get('description', '')

    if not model:
        return jsonify({"error": "No model provided"}), 400
    if not size:
        return jsonify({"error": "No size provided"}), 400
    if not description:
        return jsonify({"error": "No description provided"}), 400

    # 如果没有匹配的图片，调用 Let's API 生成一张图片
    image_url = generate_image(model, size, description)
    image_name = f"image_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{''.join(random.choices(string.digits + string.ascii_lowercase, k=10))}.png"
    image_path = upload_image(image_url, image_name)

    # 将生成的图片信息保存到数据库
    save_image_to_db(image_name, image_path, model, size, description)

    return jsonify({"code": 200, "data": [
        {"image_name": image_name,  "image_model": model,
         "image_size": size, "image_description": description}]}), 200


if __name__ == '__main__':
    # 创建上传目录（如果不存在）
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    # app.run(host='0.0.0.0', port=5000)
    app.run(host='121.40.43.143', port=5000)

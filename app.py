# -*- coding: utf-8 -*-
import os
import json
import random
import requests
from hashlib import md5
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__)

# 配置
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# 确保上传文件夹存在
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# 百度翻译API配置 - 请替换为您自己的appid和appkey
BAIDU_APPID = '你的appid'
BAIDU_APPKEY = '你的appkey'
BAIDU_ENDPOINT = 'http://api.fanyi.baidu.com'
BAIDU_PATH = '/api/trans/vip/translate'
BAIDU_URL = BAIDU_ENDPOINT + BAIDU_PATH

# 允许的图片文件扩展名
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
ALLOWED_TEXT_EXTENSIONS = {'txt'}

def allowed_file(filename, file_type='image'):
    """检查文件是否允许上传"""
    if file_type == 'image':
        allowed = ALLOWED_IMAGE_EXTENSIONS
    else:
        allowed = ALLOWED_TEXT_EXTENSIONS
        
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed

def get_image_files():
    """获取所有图片文件，按文件名自然排序"""
    files = []
    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        if allowed_file(filename, 'image'):
            files.append(filename)
    
    # 按文件名自然排序（支持数字正确排序）
    files.sort(key=lambda x: int(''.join(filter(str.isdigit, x))) if any(c.isdigit() for c in x) else x)
    return files

def make_md5(s, encoding='utf-8'):
    """生成MD5签名"""
    return md5(s.encode(encoding)).hexdigest()

def baidu_translate(text, from_lang, to_lang):
    """使用百度翻译API进行翻译"""
    if not text.strip():
        return ""
        
    # 生成盐和签名
    salt = random.randint(32768, 65536)
    sign = make_md5(BAIDU_APPID + text + str(salt) + BAIDU_APPKEY)
    
    # 构建请求参数
    payload = {
        'appid': BAIDU_APPID,
        'q': text,
        'from': from_lang,
        'to': to_lang,
        'salt': salt,
        'sign': sign
    }
    
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    try:
        # 发送请求
        response = requests.post(BAIDU_URL, params=payload, headers=headers)
        result = response.json()
        
        # 检查是否有错误
        if 'error_code' in result:
            print(f"翻译错误: {result.get('error_msg', '未知错误')}")
            return f"翻译失败: {result.get('error_msg', '未知错误')}"
            
        # 提取翻译结果
        if 'trans_result' in result and len(result['trans_result']) > 0:
            return result['trans_result'][0]['dst']
        return "未找到翻译结果"
        
    except Exception as e:
        print(f"翻译请求失败: {str(e)}")
        return f"翻译请求失败: {str(e)}"

@app.route('/')
def index():
    """主页"""
    images = get_image_files()
    image_count = len(images)  # 计算图片数量
    return render_template('index.html', images=images, image_count=image_count)

@app.route('/upload', methods=['POST'])
def upload_files():
    """上传文件"""
    if 'files' not in request.files:
        return redirect(request.url)
        
    files = request.files.getlist('files')
    
    for file in files:
        if file.filename == '':
            continue
            
        if file and (allowed_file(file.filename, 'image') or allowed_file(file.filename, 'text')):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    
    return redirect(url_for('index'))

@app.route('/get_caption/<image_name>')
def get_caption(image_name):
    """获取图片对应的提示词"""
    # 提取文件名（不含扩展名）
    base_name = os.path.splitext(image_name)[0]
    caption_file = f"{base_name}.txt"
    caption_path = os.path.join(app.config['UPLOAD_FOLDER'], caption_file)
    
    caption = ""
    if os.path.exists(caption_path):
        try:
            with open(caption_path, 'r', encoding='utf-8') as f:
                caption = f.read()
        except Exception as e:
            print(f"读取提示词文件失败: {str(e)}")
    
    return jsonify({'caption': caption})

@app.route('/save_caption/<image_name>', methods=['POST'])
def save_caption(image_name):
    """保存提示词到文件"""
    data = request.get_json()
    content = data.get('content', '')
    
    # 提取文件名（不含扩展名）
    base_name = os.path.splitext(image_name)[0]
    caption_file = f"{base_name}.txt"
    caption_path = os.path.join(app.config['UPLOAD_FOLDER'], caption_file)
    
    try:
        with open(caption_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({'success': True})
    except Exception as e:
        print(f"保存提示词文件失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/translate', methods=['POST'])
def translate_text():
    """翻译文本"""
    data = request.get_json()
    text = data.get('text', '')
    from_lang = data.get('src', 'auto')
    to_lang = data.get('dest', 'zh')
    
    # 调用百度翻译API
    translated = baidu_translate(text, from_lang, to_lang)
    return jsonify({'translated': translated})

@app.route('/clear_all')
def clear_all():
    """清空所有上传的文件"""
    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
        except Exception as e:
            print(f"删除文件失败: {str(e)}")
    
    return redirect(url_for('index'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """提供上传文件的访问"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)

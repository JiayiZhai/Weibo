#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版图片画廊生成器
使用Base64编码直接嵌入图片来避免路径问题
"""

import os
import json
import pandas as pd
from datetime import datetime
from PIL import Image
import base64
import io
import hashlib
import requests

# Load cookies if available
def load_cookies():
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            cookie_str = cfg.get('cookie', '')
            if cookie_str:
                # Convert cookie string to dict
                cookies = {}
                for item in cookie_str.split(';'):
                    if '=' in item:
                        k, v = item.strip().split('=', 1)
                        cookies[k.strip()] = v.strip()
                print("成功加载cookie配置")
                return cookies
            else:
                print("警告: config.json中未找到cookie配置")
    except Exception as e:
        print(f"加载cookie配置失败: {e}")
    return {}

COOKIES = load_cookies()

def get_image_hash(image_path):
    """获取图片文件的哈希值用于去重"""
    try:
        with open(image_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception:
        return None

def image_to_base64(image_path, max_size=(400, 400)):
    """将图片转换为Base64编码"""
    try:
        with Image.open(image_path) as img:
            # 转换为RGB模式
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # 调整图片大小
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # 保存到内存
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=85, optimize=True)
            buffer.seek(0)
            
            # 转换为Base64
            image_data = buffer.getvalue()
            base64_string = base64.b64encode(image_data).decode('utf-8')
            
            return f"data:image/jpeg;base64,{base64_string}"
    except Exception as e:
        print(f"转换图片失败 {image_path}: {e}")
        return None

def has_video(row):
    """检查是否包含视频"""
    # Check video_url field if it exists
    if 'video_url' in row and pd.notna(row['video_url']) and row['video_url'].strip() != '' and 'http' in row['video_url']:
        return True
    # 如果没有video_url列，假设所有条目都包含视频（因为已经过滤过了）
    return True

def create_simple_gallery(keyword_videos=None, html_filename=None):
    """创建简化版视频画廊"""
    try:
        if keyword_videos is None:
            # 查找最新的结果文件
            results_dir = "results"
            if not os.path.exists(results_dir):
                print("结果目录不存在")
                return None
            
            # 查找最新的汇总CSV文件
            csv_files = [f for f in os.listdir(results_dir) if f.endswith(".csv")]
            if not csv_files:
                print("未找到结果文件")
                return None
            
            # 选择最新的文件
            latest_csv = max(csv_files, key=lambda x: os.path.getmtime(os.path.join(results_dir, x)))
            csv_path = os.path.join(results_dir, latest_csv)
            
            print(f"读取结果文件: {csv_path}")
            
            # 读取CSV数据
            try:
                df = pd.read_csv(csv_path, encoding='utf-8-sig')
            except:
                df = pd.read_csv(csv_path, encoding='utf-8')
            
            if df.empty:
                print("CSV文件为空")
                return None
                
            # 修复列名中的换行符
            df.columns = [col.strip().replace('\n', '') for col in df.columns]
            
            # 确保必要的列是字符串类型
            if 'video_url' in df.columns:
                df['video_url'] = df['video_url'].fillna('').astype(str)
            else:
                df['video_url'] = ''  # 如果没有video_url列，创建空列
            df['content'] = df['content'].fillna('').astype(str)
            if 'video_cover' in df.columns:
                df['video_cover'] = df['video_cover'].fillna('').astype(str)
            
            # 去除多余的空格和换行符
            if 'video_url' in df.columns:
                df['video_url'] = df['video_url'].str.replace('\n', '').str.replace('\r', '').str.strip()
            df['content'] = df['content'].str.replace('\n', ' ').str.replace('\r', ' ').str.strip()
            if 'video_cover' in df.columns:
                df['video_cover'] = df['video_cover'].str.replace('\n', '').str.replace('\r', '').str.strip()
            
            # 不再筛选视频，处理所有微博
            print(f"找到 {len(df)} 条微博")
            
            # 按关键词分组处理视频
            keyword_videos = {}
            for keyword in df['keyword'].unique():
                keyword_data = df[df['keyword'] == keyword]
                videos = []
                for _, row in keyword_data.iterrows():
                    weibo_id = str(row.get('weibo_id', ''))
                    content = row['content']
                    # 如果内容太长，截断并添加省略号
                    if len(content) > 100:
                        content = content[:100] + "..."
                    
                    # 始终使用微博原帖链接
                    video_url = f"https://weibo.com/detail/{weibo_id}"
                    
                    videos.append({
                        'content': content,
                        'video_url': video_url,
                        'weibo_id': weibo_id
                    })
                
                if videos:  # 只添加有内容的关键词
                    keyword_videos[keyword] = videos
                    print(f"关键词 '{keyword}' 包含 {len(videos)} 条微博")
        
        if html_filename is None:
            # 如果没有提供输出文件名，生成一个默认的
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            html_filename = f'results/gallery_{timestamp}.html'
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(html_filename), exist_ok=True)
        
        # 统计视频数量
        total_videos = sum(len(videos) for videos in keyword_videos.values())
        unique_videos = len(set(video['video_url'] for videos in keyword_videos.values() for video in videos))
        
        # 生成HTML内容
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>微博内容画廊 - {datetime.now().strftime("%Y-%m-%d")}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            text-align: center;
            padding: 40px 20px;
        }}
        
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            font-weight: 300;
        }}
        
        .stats {{
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
            padding: 20px;
            margin: 20px auto;
            max-width: 600px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 20px;
            text-align: center;
        }}
        
        .stat-item {{
            font-size: 1.1em;
        }}
        
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
            display: block;
        }}
        
        .keyword-section {{
            margin: 40px 0;
            padding: 0 30px;
        }}
        
        .keyword-title {{
            font-size: 1.8em;
            color: #333;
            margin-bottom: 20px;
            padding: 15px 25px;
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            border-radius: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .keyword-stats {{
            font-size: 0.9em;
            opacity: 0.9;
        }}
        
        .video-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        
        .video-card {{
            background: white;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            position: relative;
            cursor: pointer;
            display: flex;
            flex-direction: column;
        }}
        
        .video-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 20px 40px rgba(0,0,0,0.15);
        }}
        
        .video-content-wrapper {{
            flex: 1;
            padding: 20px;
            display: flex;
            flex-direction: column;
            position: relative;
        }}
        
        .video-content {{
            font-size: 1.1em;
            color: #333;
            line-height: 1.6;
            margin-bottom: 15px;
            flex: 1;
        }}
        
        .video-play-button {{
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            text-align: center;
            font-weight: 500;
            margin-top: auto;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }}
        
        .video-play-button:hover {{
            opacity: 0.9;
        }}
        
        .video-play-button svg {{
            width: 20px;
            height: 20px;
            fill: currentColor;
        }}
        
        .footer {{
            text-align: center;
            padding: 30px;
            background: #f8f9fa;
            color: #666;
            font-size: 0.9em;
        }}
        
        @media (max-width: 768px) {{
            .video-grid {{
                grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
                gap: 15px;
            }}
            
            .keyword-title {{
                font-size: 1.4em;
                flex-direction: column;
                gap: 10px;
                text-align: center;
            }}
            
            .video-content {{
                font-size: 1em;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📱 微博内容画廊</h1>
            <div class="stats">
                <div class="stat-item">
                    <span class="stat-number">{len([k for k in keyword_videos.keys() if keyword_videos[k]])}</span>
                    关键词
                </div>
                <div class="stat-item">
                    <span class="stat-number">{unique_videos}</span>
                    唯一微博
                </div>
                <div class="stat-item">
                    <span class="stat-number">{total_videos - unique_videos}</span>
                    去重删除
                </div>
                <div class="stat-item">
                    <span class="stat-number">{((total_videos - unique_videos) / total_videos * 100) if total_videos > 0 else 0:.1f}%</span>
                    去重率
                </div>
            </div>
        </div>
        
        <div class="content">
"""
        
        # 添加每个关键词的视频
        for keyword, videos in keyword_videos.items():
            if not videos:  # 跳过没有视频的关键词
                continue
                
            html_content += f"""
            <div class="keyword-section">
                <div class="keyword-title">
                    <span>📝 {keyword}</span>
                    <span class="keyword-stats">{len(videos)} 条微博</span>
                </div>
                
                <div class="video-grid">
"""
            
            for video_data in videos:
                html_content += f"""
                    <div class="video-card" onclick="window.open('{video_data['video_url']}', '_blank')">
                        <div class="video-content-wrapper">
                            <div class="video-content">{video_data['content']}</div>
                            <div class="video-play-button">
                                <svg viewBox="0 0 24 24">
                                    <path d="M8 5v14l11-7z"/>
                                </svg>
                                查看微博详情
                            </div>
                        </div>
                    </div>
"""
            
            html_content += """
                </div>
            </div>
"""
        
        # 添加底部
        html_content += f"""
        </div>
        
        <div class="footer">
            <p>🎯 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <p>📊 已智能去重，仅显示唯一微博</p>
        </div>
    </div>
</body>
</html>
"""
        
        # 保存HTML文件
        with open(html_filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"微博画廊已保存到: {html_filename}")
        print(f"去重统计: 总计 {total_videos} 条微博，保留 {unique_videos} 条唯一微博，删除 {total_videos - unique_videos} 条重复微博")
        
        return html_filename
        
    except Exception as e:
        print(f"生成视频画廊时出错: {e}")
        return None

if __name__ == "__main__":
    create_simple_gallery() 
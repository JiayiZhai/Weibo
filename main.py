#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import logging
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from fetch import WeiboSpider
from keyword_manager import KeywordManager
from ml_analyzer import MLAnalyzer
import time
import base64
from PIL import Image
import io
import re
import unicodedata

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('weibo_spider.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def load_config():
    """加载配置文件"""
    config_file = "config.json"
    default_config = {
        "cookie": "",
        "default_pages": 5,
        "min_score": 80,
        "min_likes": 500,  # 添加最低点赞数参数
        "download_media": False,
        "max_retries": 3,
        "retry_delay": 5,
        "thread_pool_size": 4,
        "proxy": None
    }
    
    try:
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # 确保所有必要的配置项都存在
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
        else:
            config = default_config
            # 保存默认配置
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        
        return config
    except Exception as e:
        logging.error(f"加载配置文件时出错: {e}")
        return default_config

def save_config(config):
    """保存配置到文件"""
    try:
        with open("config.json", 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"保存配置文件时出错: {e}")

def image_to_base64(image_path, max_size=(300, 300)):
    """
    将图片转换为Base64编码字符串
    
    参数:
    - image_path: 图片文件路径
    - max_size: 最大尺寸(宽, 高)，用于压缩图片
    
    返回:
    - Base64编码字符串
    """
    try:
        if not os.path.exists(image_path):
            return ""
        
        # 打开图片并调整大小以减少文件大小
        with Image.open(image_path) as img:
            # 转换为RGB（如果是RGBA等格式）
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # 计算缩放比例，保持长宽比
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # 将图片保存到内存中
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=85, optimize=True)
            buffer.seek(0)
            
            # 转换为Base64
            image_data = buffer.getvalue()
            base64_string = base64.b64encode(image_data).decode('utf-8')
            
            return f"data:image/jpeg;base64,{base64_string}"
    
    except Exception as e:
        logging.warning(f"转换图片到Base64时出错 {image_path}: {e}")
        return ""

def add_image_data_to_weibos(weibos):
    """
    为微博数据添加图片的Base64编码
    
    参数:
    - weibos: 微博数据列表
    
    返回:
    - 包含图片数据的微博列表
    """
    for weibo in weibos:
        image_paths = weibo.get('image_paths', '')
        base64_images = []
        
        if image_paths:
            paths = image_paths.split('|')
            for path in paths:
                if path and os.path.exists(path):
                    base64_data = image_to_base64(path)
                    if base64_data:
                        base64_images.append(base64_data)
        
        # 添加Base64图片数据到微博信息中
        weibo['image_base64'] = '|'.join(base64_images) if base64_images else ''
        weibo['image_count'] = len(base64_images)
    
    return weibos

def download_filtered_media(spider, filtered_weibos, keyword):
    """
    为通过筛选的高质量微博下载图片
    
    参数:
    - spider: 爬虫实例
    - filtered_weibos: 筛选后的微博列表
    - keyword: 关键词
    """
    downloaded_count = 0
    for weibo in filtered_weibos:
        if weibo.get('has_images', False):
            image_urls = weibo.get('image_urls', '').split('|')
            image_paths = []
            
            for url in image_urls:
                if url:
                    local_path = spider.download_media(url, 'image', keyword, weibo['weibo_id'])
                    if local_path:
                        image_paths.append(local_path)
                        downloaded_count += 1
                    time.sleep(0.5)  # 避免请求过快
            
            # 更新微博数据中的本地路径信息
            weibo['image_paths'] = '|'.join(image_paths)
    
    return downloaded_count

def parse_weibo_time(time_str, now=None):
    """
    解析微博时间字符串为 datetime 对象。
    支持格式：'5分钟前'、'今天 12:34'、'昨天 12:34'、'2024-05-23 12:34'等。
    """
    if now is None:
        now = datetime.now()
    time_str = str(time_str).strip()
    if not time_str or time_str == '未知时间':
        return None
    try:
        if '分钟前' in time_str:
            minutes = int(time_str.replace('分钟前', '').strip())
            return now - timedelta(minutes=minutes)
        elif '小时前' in time_str:
            hours = int(time_str.replace('小时前', '').strip())
            return now - timedelta(hours=hours)
        elif '今天' in time_str:
            t = time_str.replace('今天', '').strip()
            dt = datetime.strptime(t, '%H:%M')
            return now.replace(hour=dt.hour, minute=dt.minute, second=0, microsecond=0)
        elif '昨天' in time_str:
            t = time_str.replace('昨天', '').strip()
            dt = datetime.strptime(t, '%H:%M')
            dt = now.replace(hour=dt.hour, minute=dt.minute, second=0, microsecond=0) - timedelta(days=1)
            return dt
        elif '-' in time_str:
            # 可能是 '05-23 12:34' 或 '2024-05-23 12:34'
            if len(time_str) == 11:  # '05-23 12:34'
                t = f"{now.year}-{time_str}"
                return datetime.strptime(t, '%Y-%m-%d %H:%M')
            elif len(time_str) == 16:  # '2024-05-23 12:34'
                return datetime.strptime(time_str, '%Y-%m-%d %H:%M')
    except Exception:
        pass
    return None

def process_keyword(keyword, spider, ml_analyzer, config, now, keyword_to_type):
    """处理单个关键词的爬取和分析"""
    try:
        logging.info(f"开始搜索关键词: {keyword}")
        
        # 获取关键词的分类
        keyword_type = keyword_to_type.get(keyword, "unknown")
        logging.info(f"关键词 '{keyword}' 的分类: {keyword_type}")
        
        # 获取搜索结果 - 强制关闭媒体下载
        results = spider.search_keyword(
            keyword, 
            pages=config["default_pages"], 
            start_page=config["start_page"],
            download_media=False  # 强制关闭媒体下载
        )
        
        if not results:
            logging.warning(f"未找到关键词 '{keyword}' 的相关微博")
            return None
        
        logging.info(f"获取到 {len(results)} 条微博")
        
        # ====== 筛选最近两天的微博（不再强制要求视频） ======
        now_dt = datetime.now()
        two_days_ago = now_dt - timedelta(days=2)
        filtered_by_time = []
        for weibo in results:
            dt = parse_weibo_time(weibo.get('publish_time', ''), now=now_dt)
            if dt and dt >= two_days_ago:
                filtered_by_time.append(weibo)
        logging.info(f"筛选后剩余 {len(filtered_by_time)} 条最近两天的微博")
        if not filtered_by_time:
            logging.warning(f"最近两天没有关键词 '{keyword}' 的相关微博")
            return None
        # ====== 后续分析用 filtered_by_time 替换 results ======
        
        # 应用机器学习分析
        logging.info("正在进行机器学习分析...")
        analysis_result = ml_analyzer.analyze_weibos(
            filtered_by_time, 
            min_score=config["min_score"],
            min_likes=config["min_likes"],  # 传递最低点赞数参数
            min_comments=config["min_comments"] if "min_comments" in config else 0,
            min_forwards=config["min_forwards"] if "min_forwards" in config else 0
        )
        
        if not analysis_result or "filtered_weibos" not in analysis_result:
            logging.warning(f"机器学习分析未返回有效结果")
            return None
        
        filtered_results = analysis_result["filtered_weibos"]
        logging.info(f"机器学习分析后保留 {len(filtered_results)} 条高质量微博")
        
        # 为每条微博添加关键词分类信息
        for weibo in filtered_results:
            weibo['type'] = keyword_type
        
        # 如果启用了媒体下载，为筛选后的微博下载图片 - 移除此功能
        if config["download_media"]:
            logging.info(f"媒体下载已禁用")
        
        # 移除图片处理相关代码
        if config["download_media"]:
            logging.info(f"图片处理已禁用")
        
        # 保存结果
        result_dir = "results"
        os.makedirs(result_dir, exist_ok=True)
        
        # 保存过滤后的微博数据
        df = pd.DataFrame(filtered_results)
        df = clean_and_reorder_dataframe(df)  # 清理和重新排列列
        # 按点赞量降序排序
        df = df.sort_values(by='likes', ascending=False)
        keyword_file = f"{result_dir}/{keyword}_{now}.csv"
        df.to_csv(keyword_file, index=False, encoding='utf-8-sig')
        logging.info(f"已保存过滤后的结果到 {keyword_file}")
        
        # 保存分析结果
        analysis_file = f"{result_dir}/{keyword}_analysis_{now}.json"
        with open(analysis_file, 'w', encoding='utf-8') as f:
            json.dump(analysis_result, f, ensure_ascii=False, indent=2)
        logging.info(f"已保存分析结果到 {analysis_file}")
        
        # 输出热门话题
        if "trending_topics" in analysis_result:
            logging.info("\n热门话题:")
            for topic in analysis_result["trending_topics"]:
                logging.info(f"- {topic['keyword']} (热度: {topic['score']:.2f}, 相关微博数: {topic['weibo_count']})")
        
        return filtered_results
        
    except Exception as e:
        logging.error(f"处理关键词 '{keyword}' 时出错: {e}")
        return None

def load_keyword_classifications():
    """
    加载关键词分类信息
    
    返回:
    - 关键词到分类的映射字典
    """
    classification_file = "keyword and classification.txt"
    keyword_to_type = {}
    
    try:
        if os.path.exists(classification_file):
            df = pd.read_csv(classification_file, encoding='utf-8')
            # 创建关键词到分类的映射
            for _, row in df.iterrows():
                keyword = row.iloc[0]  # 第一列是关键词
                classification = row.iloc[1]  # 第二列是分类
                keyword_to_type[keyword] = classification
            
            logging.info(f"成功加载 {len(keyword_to_type)} 个关键词分类")
        else:
            logging.warning(f"分类文件 {classification_file} 不存在")
    
    except Exception as e:
        logging.error(f"加载关键词分类时出错: {e}")
    
    return keyword_to_type

def clean_and_reorder_dataframe(df):
    """清理并重新排序DataFrame"""
    # 确保所有必要的列都存在
    required_columns = ['weibo_id', 'content', 'publish_time', 'reposts_count', 'comments_count', 
                        'attitudes_count', 'post_link', 'video_url', 'video_cover']
    
    # 添加空列，如果不存在
    for col in required_columns:
        if col not in df.columns:
            df[col] = ''
    
    # 删除用户名字段
    if 'user_name' in df.columns:
        df = df.drop(columns=['user_name'])
    
    # 确保post_link列非空，如果为空则使用weibo_id生成
    if 'weibo_id' in df.columns:
        mask = (df['post_link'].isna()) | (df['post_link'] == '')
        df.loc[mask, 'post_link'] = df.loc[mask, 'weibo_id'].apply(
            lambda x: f'https://weibo.com/detail/{x}'
        )
    
    # 清理content，保留纯文本
    if 'content' in df.columns:
        # 移除HTML标签
        df['content'] = df['content'].astype(str).replace(r'<[^>]*>', '', regex=True)
        # 移除微博特殊标记如[表情]
        df['content'] = df['content'].replace(r'\[.*?\]', '', regex=True)
        # 移除链接
        df['content'] = df['content'].replace(r'http[s]?://\S+', '', regex=True)
        # 移除多余空格和换行
        df['content'] = df['content'].replace(r'\s+', ' ', regex=True).str.strip()
        # 移除特殊Unicode字符
        df['content'] = df['content'].replace(r'[\u200b-\u200f\u2028-\u202f\u205f-\u206f]', '', regex=True)
        # 移除"​​​"结尾（这是微博文本常见的结尾）
        df['content'] = df['content'].replace(r'​+$', '', regex=True)
    
    # 重新排序列，优先显示重要信息
    ordered_columns = ['keyword'] + required_columns
    
    # 只保留在ordered_columns中的列
    existing_columns = [col for col in ordered_columns if col in df.columns]
    
    # 如果有其他额外的列，也保留
    extra_columns = [col for col in df.columns if col not in ordered_columns]
    
    # 合并列顺序
    final_columns = existing_columns + extra_columns
    
    return df[final_columns]

def read_keywords(file_path):
    """读取关键词列表文件"""
    try:
        # 如果文件路径是 "keywords.txt"，改为从 "keyword and classification.txt" 中读取
        if file_path == 'keywords.txt':
            classification_file = "keyword and classification.txt"
            if os.path.exists(classification_file):
                df = pd.read_csv(classification_file, encoding='utf-8')
                # 从第一列（关键词列）提取关键词
                if '关键词' in df.columns:
                    return df['关键词'].dropna().tolist()
                else:
                    # 如果没有列名，就假设第一列是关键词
                    return df.iloc[:, 0].dropna().tolist()
            else:
                print(f"文件 {classification_file} 不存在")
                return []
        else:
            # 原始的从文本文件读取方式
            with open(file_path, 'r', encoding='utf-8') as f:
                # 过滤掉空行
                return [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"读取{file_path}失败: {str(e)}")
        return []

def read_user_urls(file_path):
    """读取用户URL列表文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            # 过滤掉空行和注释行
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except Exception as e:
        print(f"读取{file_path}失败: {str(e)}")
        return []

def has_video(row):
    # Check video_url field
    if pd.notna(row['video_url']) and row['video_url'].strip() != '':
        return True
    return False

def process_weibo_data(df):
    # Add has_video column and filter
    df['has_video'] = df.apply(has_video, axis=1)
    return df[df['has_video'] == True].drop('has_video', axis=1)

def main():
    # 加载配置
    config = load_config()
    
    # 读取关键词列表
    keywords = read_keywords('keywords.txt')
    if not keywords:
        logging.error("未在keywords.txt中找到任何关键词")
        return

    logging.info(f"从keywords.txt中读取到 {len(keywords)} 个关键词")

    # 读取关键词分类
    keyword_to_type = load_keyword_classifications()
    logging.info(f"加载了 {len(keyword_to_type)} 个关键词分类信息")

    # 读取用户URL列表
    user_urls = read_user_urls('user_urls.txt')
    if not user_urls:
        logging.error("user_urls.txt中没有找到有效的用户URL")
        return

    logging.info(f"从user_urls.txt中读取到 {len(user_urls)} 个用户URL")

    # 创建爬虫实例
    spider = WeiboSpider()

    # 创建结果目录
    result_dir = "results"
    os.makedirs(result_dir, exist_ok=True)

    # 当前时间，用于文件命名
    now = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 存储所有结果
    all_results = []

    # 处理每个用户
    for i, user_url in enumerate(user_urls, 1):
        logging.info(f"\n处理第 {i}/{len(user_urls)} 个用户: {user_url}")
        user_id = spider._extract_user_id(user_url) or f"user_{i}"
        
        # 对每个关键词进行搜索
        for keyword in keywords:
            logging.info(f"\n搜索关键词: {keyword}")
            try:
                # 爬取该用户的微博
                results = spider.search_keyword(
                    user_url=user_url,
                    keyword=keyword,
                    pages=1,  # 固定为1页
                    download_media=config["download_media"]
                )
                
                if results:
                    # 为每条微博添加用户ID和关键词信息
                    for result in results:
                        result['user_id'] = user_id
                        result['keyword'] = keyword
                    all_results.extend(results)
                    logging.info(f"找到 {len(results)} 条包含关键词 '{keyword}' 的微博")
                else:
                    logging.info(f"未找到包含关键词 '{keyword}' 的微博")
                
            except Exception as e:
                logging.error(f"处理关键词 {keyword} 时出错: {str(e)}")
                continue

    # 保存所有结果到CSV文件
    if all_results:
        try:
            # 转换为DataFrame
            df_all = pd.DataFrame(all_results)
            
            # 清理和重新排序DataFrame
            df_all = clean_and_reorder_dataframe(df_all)
            
            # 添加分类信息
            df_all['keyword_type'] = df_all['keyword'].map(keyword_to_type).fillna('other')
            
            # 先按关键词分类排序（show类别优先），然后按点赞量降序排序
            df_all['is_show'] = (df_all['keyword_type'] == 'show').astype(int)
            df_all = df_all.sort_values(by=['is_show', 'attitudes_count'], ascending=[False, False])
            
            # 删除辅助排序列
            if 'is_show' in df_all.columns:
                df_all = df_all.drop(columns=['is_show'])
            if 'keyword_type' in df_all.columns:
                df_all = df_all.drop(columns=['keyword_type'])
            
            # 不再过滤视频，保留所有微博
            
            # 保存为CSV
            output_file = os.path.join(result_dir, f"all_results_{now}.csv")
            df_all.to_csv(output_file, index=False, encoding='utf-8-sig')
            
            # 删除多余字段，只保留指定字段
            keep_columns = ['keyword', 'weibo_id', 'content', 'publish_time', 'reposts_count', 'comments_count', 'attitudes_count', 'post_link']
            existing_keep_columns = [col for col in keep_columns if col in df_all.columns]
            df_filtered = df_all[existing_keep_columns]
            df_filtered.to_csv(output_file, index=False, encoding='utf-8-sig')
            
            logging.info(f"\n已保存所有微博到: {output_file}")
            logging.info(f"总共获取到 {len(df_all)} 条微博")

            # 自动生成图片画廊
            try:
                from create_simple_gallery import create_simple_gallery
                logging.info("\n正在生成图片画廊...")
                html_file = create_simple_gallery()
                
                if html_file:
                    # 获取完整路径
                    current_dir = os.getcwd()
                    full_path = os.path.join(current_dir, html_file)
                    
                    # 在终端输出HTML文件信息
                    print("\n" + "="*60)
                    print("🎨 图片画廊生成完成！")
                    print("="*60)
                    print(f"📁 文件位置: {html_file}")
                    print(f"🔗 完整路径: {full_path}")
                    print(f"🌐 浏览器访问: file://{full_path}")
                    print("\n💡 使用方法:")
                    print(f"   • 直接双击打开: {html_file}")
                    print(f"   • 或运行命令: open {html_file}")
                    print("="*60)
                    
                    # 询问是否立即打开
                    try:
                        user_input = input("\n是否立即在浏览器中打开画廊？(y/N): ").strip().lower()
                        if user_input in ['y', 'yes', '是']:
                            import webbrowser
                            webbrowser.open(f'file://{full_path}')
                            print("✅ 已在浏览器中打开图片画廊")
                    except (EOFError, KeyboardInterrupt):
                        print("\n跳过打开画廊")
                        
            except ImportError:
                logging.warning("图片画廊生成器模块未找到，跳过画廊生成")
            except Exception as e:
                pass  # 忽略画廊生成错误
        except Exception as e:
            logging.error(f"保存结果到CSV时出错: {str(e)}")
    else:
        logging.warning("未获取到任何结果")

if __name__ == '__main__':
    main()

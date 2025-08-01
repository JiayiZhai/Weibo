#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import time
import requests
import re
from datetime import datetime
import random
from lxml import etree
from tqdm import tqdm
from fake_useragent import UserAgent

class WeiboSpider:
    def __init__(self):
        self.seen_weibos = set()
        self.downloaded_images = set()  # 跟踪已下载的图片URL
        self.ua = UserAgent()
        self.base_url = "https://s.weibo.com/weibo"
        self.headers = {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
        }
        
        # 从config.json读取配置
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
                cookie_str = config.get('cookie', '')
                if cookie_str:
                    self.set_cookies(cookie_str)
                    print("已从config.json加载cookie配置")
                else:
                    print("警告: config.json中未找到cookie配置")
                    self.cookies = {}
        except Exception as e:
            print(f"读取config.json失败: {str(e)}")
            self.cookies = {}
        
        # 创建下载目录
        self.media_dir = "media"
        os.makedirs(self.media_dir, exist_ok=True)
    
    def _get_random_delay(self):
        """生成随机延迟，避免被检测为爬虫"""
        return random.uniform(1, 3)
    
    def _update_headers(self):
        """更新请求头，防止被检测"""
        self.headers["User-Agent"] = self.ua.random
    
    def download_media(self, url, media_type, keyword, weibo_id):
        """
        下载媒体文件（图片或视频）
        
        参数:
        - url: 媒体文件URL
        - media_type: 媒体类型 ('image' 或 'video')
        - keyword: 搜索关键词
        - weibo_id: 微博ID
        
        返回:
        - 本地文件路径
        """
        try:
            # 检查是否已经下载过这个URL
            if url in self.downloaded_images:
                print(f"图片已下载过，跳过: {url}")
                return ""
            
            # print(f"DEBUG - 开始下载: {url}")
            
            # 创建关键词专用目录
            keyword_dir = os.path.join(self.media_dir, keyword)
            os.makedirs(keyword_dir, exist_ok=True)
            
            # 从URL中提取更具体的标识符
            url_parts = url.split('/')
            unique_id = url_parts[-1].split('?')[0] if url_parts else str(int(time.time()))
            
            # 获取文件扩展名
            file_ext = url.split('.')[-1].split('?')[0]
            if file_ext not in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'mp4', 'mov']:
                file_ext = 'jpg'  # 默认为jpg
            
            # 生成更唯一的文件名
            timestamp = int(time.time() * 1000)  # 使用毫秒级时间戳
            random_suffix = random.randint(1000, 9999)
            filename = f"{media_type}_{weibo_id}_{unique_id}_{timestamp}_{random_suffix}.{file_ext}"
            file_path = os.path.join(keyword_dir, filename)
            
            # print(f"DEBUG - 生成文件名: {filename}")
            
            # 下载文件
            headers = self.headers.copy()
            headers['Referer'] = 'https://weibo.com/'
            
            response = requests.get(url, headers=headers, timeout=30, stream=True)
            response.raise_for_status()
            
            # 检查内容类型
            content_type = response.headers.get('content-type', '')
            # print(f"DEBUG - 内容类型: {content_type}")
            
            # 保存文件
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # 检查文件大小
            file_size = os.path.getsize(file_path)
            print(f"下载成功: {filename} (大小: {file_size} bytes)")
            
            # 记录已下载的URL
            self.downloaded_images.add(url)
            
            return file_path
            
        except Exception as e:
            print(f"下载失败 {url}: {e}")
            return ""
    
    def extract_images(self, card, keyword, weibo_id):
        """
        提取微博图片链接并可选下载
        
        参数:
        - card: 微博卡片元素
        - keyword: 搜索关键词
        - weibo_id: 微博ID
        
        返回:
        - (image_urls, local_paths) 元组
        """
        # 图片容器通常在这些位置
        image_nodes = card.xpath('.//div[contains(@class, "media-pic")]//img/@src') or \
                     card.xpath('.//div[@node-type="feed_list_media_prev"]//img/@src') or \
                     card.xpath('.//img[contains(@class, "pic")]/@src')
        
        # Debug: 打印找到的图片节点
        if image_nodes:
            print(f"微博{weibo_id}找到{len(image_nodes)}个图片")
        
        # 清理URL地址
        image_urls = []
        local_paths = []
        
        for url in image_nodes:
            if url.startswith('//'):
                url = 'https:' + url
            
            # 将thumbnail链接转换为原图链接
            if '/thumb150/' in url:
                url = url.replace('/thumb150/', '/large/')
            elif '/bmiddle/' in url:
                url = url.replace('/bmiddle/', '/large/')
            
            # print(f"DEBUG - 处理后的图片URL: {url}")
            image_urls.append(url)
            
            # 如果启用了媒体下载，则下载图片
            if self.download_media_enabled:
                local_path = self.download_media(url, 'image', keyword, weibo_id)
                if local_path:
                    local_paths.append(local_path)
                time.sleep(0.5)  # 短暂延迟，避免请求过快
        
        return image_urls, local_paths
    
    def extract_videos(self, card, keyword, weibo_id):
        """
        提取微博视频链接 - 简化版中不会下载
        """
        # 找视频链接的容器
        video_nodes = card.xpath('.//div[contains(@class, "media-video")]')
        
        video_urls = []
        for node in video_nodes:
            video_url = node.xpath('./@data-url')
            if not video_url:
                # 尝试其他可能的属性
                video_url = node.xpath('./video/@src') or node.xpath('./@action-data')
            
            if video_url:
                url = video_url[0]
                if url.startswith('//'):
                    url = 'https:' + url
                
                video_urls.append(url)
        
        return video_urls, []  # 返回空列表作为本地路径，不下载
    
    def _extract_user_id(self, user_url):
        """从用户URL中提取用户ID"""
        # 处理不同格式的用户URL
        patterns = [
            r'weibo\.com/u/(\d+)',
            r'weibo\.com/(\d+)',
            r'weibo\.com/p/(\d+)',
            r'weibo\.com/profile/(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, user_url)
            if match:
                return match.group(1)
        return None

    def search_keyword(self, user_url, keyword, pages=5, start_page=1, download_media=False):
        """
        在用户主页中搜索包含关键词的微博
        
        参数:
        - user_url: 用户主页URL
        - keyword: 搜索关键词
        - pages: 爬取页数
        - start_page: 开始爬取的页码，默认从第1页开始
        - download_media: 是否下载媒体文件
        
        返回:
        - 搜索结果列表
        """
        results = []
        self.download_media_enabled = download_media
        
        user_id = self._extract_user_id(user_url)
        if not user_id:
            print(f"无法从URL中提取用户ID: {user_url}")
            return results
        
        end_page = start_page + pages - 1
        print(f"准备在用户 {user_id} 的主页中搜索关键词 '{keyword}', 计划爬取 {start_page} 到 {end_page} 页")
        
        for page in tqdm(range(start_page, end_page + 1), desc="爬取进度"):
            try:
                # 构建用户微博列表页URL
                search_url = f"https://weibo.com/ajax/statuses/mymblog?uid={user_id}&page={page}&feature=0"
                
                # 更新请求头
                self._update_headers()
                
                # 发送请求
                response = requests.get(
                    search_url, 
                    headers=self.headers, 
                    cookies=self.cookies, 
                    timeout=10
                )
                
                # 检查响应状态
                if response.status_code != 200:
                    print(f"请求失败，状态码: {response.status_code}")
                    continue
                
                try:
                    data = response.json()
                    weibo_list = data.get('data', {}).get('list', [])
                    
                    if not weibo_list:
                        print(f"页面 {page} 未找到微博内容，可能已到达末页")
                        break
                    
                    for weibo in weibo_list:
                        # 获取微博文本内容
                        content = weibo.get('text_raw', '')
                        
                        user_name = weibo.get('user', {}).get('screen_name', '')

                        # 检查是否包含关键词（不区分大小写）
                        if keyword.lower() not in content.lower():
                            continue
                            
                        weibo_id = str(weibo.get('id', '未知ID'))
                        
                        # 检查是否已经爬取过这条微博
                        if weibo_id in self.seen_weibos:
                            continue
                        
                        self.seen_weibos.add(weibo_id)
                        
                        # 获取微博详细信息
                        try:
                            detail_url = f"https://weibo.com/ajax/statuses/show?id={weibo_id}"
                            response = requests.get(detail_url, headers=self.headers, cookies=self.cookies, timeout=10)
                            if response.status_code == 200:
                                detail_data = response.json()
                                if detail_data:
                                    weibo = detail_data
                                    print(f"成功获取微博详细信息: {weibo_id}")
                        except Exception as e:
                            print(f"获取微博详细信息时出错: {e}")
                        
                        # 提取图片URL
                        pic_ids = weibo.get('pic_ids', [])
                        image_urls = [f"https://wx1.sinaimg.cn/large/{pic_id}.jpg" for pic_id in pic_ids]
                        local_paths = []
                        
                        # 如果启用了媒体下载，下载图片
                        if download_media and image_urls:
                            for url in image_urls:
                                local_path = self.download_media(url, 'image', keyword, weibo_id)
                                if local_path:
                                    local_paths.append(local_path)
                                time.sleep(0.5)  # 短暂延迟，避免请求过快
                        
                        weibo_data = {
                            'weibo_id': weibo_id,
                            'user_name': user_name,
                            'user_id': user_id,
                            'content': content,
                            'publish_time': weibo.get('created_at', '未知时间'),
                            'reposts_count': weibo.get('reposts_count', 0),
                            'comments_count': weibo.get('comments_count', 0),
                            'attitudes_count': weibo.get('attitudes_count', 0),
                            'source': weibo.get('source', '未知来源'),
                            'keyword': keyword,
                            'image_urls': image_urls,
                            'local_image_paths': local_paths if download_media else [],
                            'video_url': '',  # 初始化视频URL
                            'video_cover': ''  # 初始化视频封面URL
                        }

                        # 检查是否包含视频
                        page_info = weibo.get('page_info', {})
                        if page_info and page_info.get('type') == 'video':
                            media_info = page_info.get('media_info', {})
                            # 尝试从urls字段获取视频链接
                            urls = page_info.get('urls', {})
                            if urls:
                                weibo_data['video_url'] = urls.get('mp4_720p_mp4', '') or urls.get('mp4_hd_url', '') or urls.get('mp4_sd_url', '') or urls.get('stream_url', '')
                            # 如果urls中没有，再尝试media_info
                            if not weibo_data['video_url']:
                                weibo_data['video_url'] = media_info.get('mp4_720p_mp4', '') or media_info.get('mp4_hd_url', '') or media_info.get('mp4_sd_url', '') or media_info.get('stream_url', '')
                            # 如果还是没有，尝试play_url
                            if not weibo_data['video_url']:
                                weibo_data['video_url'] = page_info.get('play_url', '') or page_info.get('media_url', '') or page_info.get('url', '')
                            weibo_data['video_cover'] = page_info.get('page_pic', {}).get('url', '') or page_info.get('page_pic', '')
                            print(f"找到视频微博，视频链接: {weibo_data['video_url']}")

                        # 检查mix_media_info中的视频
                        mix_media_info = weibo.get('mix_media_info', {})
                        if mix_media_info:
                            media_items = mix_media_info.get('items', [])
                            for item in media_items:
                                if item.get('type') == 'video':
                                    media_info = item.get('data', {}).get('media_info', {})
                                    urls = item.get('data', {}).get('urls', {})
                                    if not weibo_data['video_url']:  # 如果之前没有设置视频URL
                                        if urls:
                                            weibo_data['video_url'] = urls.get('mp4_720p_mp4', '') or urls.get('mp4_hd_url', '') or urls.get('mp4_sd_url', '') or urls.get('stream_url', '')
                                        if not weibo_data['video_url']:
                                            weibo_data['video_url'] = media_info.get('mp4_720p_mp4', '') or media_info.get('mp4_hd_url', '') or media_info.get('mp4_sd_url', '') or media_info.get('stream_url', '')
                                        if not weibo_data['video_url']:
                                            weibo_data['video_url'] = item.get('data', {}).get('play_url', '') or item.get('data', {}).get('media_url', '') or item.get('data', {}).get('url', '')
                                    if not weibo_data['video_cover']:  # 如果之前没有设置封面URL
                                        cover_url = item.get('data', {}).get('cover_image', {}).get('url', '') or item.get('data', {}).get('cover_image_url', '')
                                        weibo_data['video_cover'] = cover_url
                                    print(f"在mix_media_info中找到视频，视频链接: {weibo_data['video_url']}")
                                    break  # 找到一个视频就足够了

                        # 检查视频组件
                        if weibo.get('retweeted_status', {}).get('page_info', {}).get('type') == 'video':
                            page_info = weibo.get('retweeted_status', {}).get('page_info', {})
                            media_info = page_info.get('media_info', {})
                            urls = page_info.get('urls', {})
                            if not weibo_data['video_url']:
                                if urls:
                                    weibo_data['video_url'] = urls.get('mp4_720p_mp4', '') or urls.get('mp4_hd_url', '') or urls.get('mp4_sd_url', '') or urls.get('stream_url', '')
                                if not weibo_data['video_url']:
                                    weibo_data['video_url'] = media_info.get('mp4_720p_mp4', '') or media_info.get('mp4_hd_url', '') or media_info.get('mp4_sd_url', '') or media_info.get('stream_url', '')
                                if not weibo_data['video_url']:
                                    weibo_data['video_url'] = page_info.get('play_url', '') or page_info.get('media_url', '') or page_info.get('url', '')
                            if not weibo_data['video_cover']:
                                weibo_data['video_cover'] = page_info.get('page_pic', {}).get('url', '') or page_info.get('page_pic', '')
                            print(f"在转发内容中找到视频，视频链接: {weibo_data['video_url']}")

                        # 检查短链接中的视频
                        if not weibo_data['video_url']:
                            content = weibo_data['content']
                            short_urls = re.findall(r'http://t\.cn/[A-Za-z0-9]+', content)
                            for short_url in short_urls:
                                try:
                                    # 获取短链接的详细信息
                                    detail_url = f"https://weibo.com/ajax/statuses/show?id={weibo_id}"
                                    response = requests.get(detail_url, headers=self.headers, cookies=self.cookies, timeout=10)
                                    if response.status_code == 200:
                                        detail_data = response.json()
                                        if detail_data:
                                            # 检查是否有视频信息
                                            page_info = detail_data.get('page_info', {})
                                            if page_info and page_info.get('type') == 'video':
                                                media_info = page_info.get('media_info', {})
                                                weibo_data['video_url'] = media_info.get('mp4_720p_mp4', '') or media_info.get('mp4_hd_url', '') or media_info.get('mp4_sd_url', '') or media_info.get('stream_url', '')
                                                if not weibo_data['video_url']:
                                                    weibo_data['video_url'] = page_info.get('play_url', '') or page_info.get('media_url', '') or page_info.get('url', '')
                                                weibo_data['video_cover'] = page_info.get('page_pic', {}).get('url', '') or page_info.get('page_pic', '')
                                                print(f"在短链接中找到视频，视频链接: {weibo_data['video_url']}")
                                                break
                                except Exception as e:
                                    print(f"解析短链接时出错: {e}")
                                    continue

                        # 如果还是没有找到视频URL，但是有短链接，就用短链接作为视频URL
                        if not weibo_data['video_url'] and short_urls:
                            weibo_data['video_url'] = short_urls[0]
                            weibo_data['video_cover'] = 'https://h5.sinaimg.cn/upload/100/1493/2020/05/09/timeline_card_small_video_default.png'
                            print(f"使用短链接作为视频链接: {weibo_data['video_url']}")
                        
                        results.append(weibo_data)
                        print(f"找到匹配关键词 '{keyword}' 的微博: {content[:50]}...")
                
                except json.JSONDecodeError:
                    print(f"解析JSON失败，页面 {page}")
                    continue
                
                # 添加延迟
                time.sleep(self._get_random_delay())
                
            except Exception as e:
                print(f"爬取页面 {page} 时出错: {str(e)}")
                continue
        
        print(f"\n在用户 {user_id} 的主页中共找到 {len(results)} 条包含关键词 '{keyword}' 的微博")
        return results
    
    def set_cookies(self, cookie_str):
        """
        设置Cookie，提高爬取效果
        
        参数:
        - cookie_str: Cookie字符串
        """
        if not cookie_str:
            return
        
        # 解析Cookie字符串为字典
        cookies = {}
        for item in cookie_str.split(';'):
            if '=' in item:
                key, value = item.strip().split('=', 1)
                cookies[key] = value
        
        self.cookies = cookies
        print("Cookie设置成功")

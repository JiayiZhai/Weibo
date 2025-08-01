#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import json
import time
import random
import requests
import os
from lxml import etree
from tqdm import tqdm
from fake_useragent import UserAgent

class WeiboSpider:
    def __init__(self):
        self.seen_weibos = set()
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
        
        # 从config.json读取cookie
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
        
        # 创建下载目录 (保留但不会使用)
        self.media_dir = "media"
        os.makedirs(self.media_dir, exist_ok=True)
        
        # 创建结果目录
        self.results_dir = "results"
        os.makedirs(self.results_dir, exist_ok=True)
    
    def _get_random_delay(self):
        """生成随机延迟，避免被检测为爬虫"""
        return random.uniform(1, 3)
    
    def _update_headers(self):
        """更新请求头，防止被检测"""
        self.headers["User-Agent"] = self.ua.random
    
    # 以下媒体下载函数保留但在简化版中不会被调用
    def download_media(self, url, media_type, keyword, weibo_id):
        """
        下载媒体文件（图片或视频）- 简化版中不会使用此功能
        """
        return ""
    
    def extract_images(self, card, keyword, weibo_id):
        """
        提取微博图片链接 - 简化版中不会下载
        """
        # 图片容器通常在这些位置
        image_nodes = card.xpath('.//div[contains(@class, "media-pic")]//img/@src')
        
        # 有时候图片在另一个容器里
        if not image_nodes:
            image_nodes = card.xpath('.//div[@node-type="feed_list_media_prev"]//img/@src')
        
        # 清理URL地址
        image_urls = []
        for url in image_nodes:
            if url.startswith('//'):
                url = 'https:' + url
            
            # 将thumbnail链接转换为原图链接
            if '/thumb150/' in url:
                url = url.replace('/thumb150/', '/large/')
            
            image_urls.append(url)
        
        return image_urls, []  # 返回空列表作为本地路径，不下载
    
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
    
    def search_keyword(self, user_url, keyword, pages, start_page=1, download_media=False):
        """
        在用户主页中搜索包含关键词的微博
        
        参数:
        - user_url: 用户主页URL
        - keyword: 搜索关键词
        - pages: 爬取页数
        - start_page: 开始爬取的页码，默认从第1页开始
        - download_media: 媒体下载标志(简化版中忽略此参数)
        
        返回:
        - 搜索结果列表
        """
        results = []
        self.download_media_enabled = False  # 强制关闭媒体下载
        
        user_id = self._extract_user_id(user_url)
        if not user_id:
            print(f"无法从URL中提取用户ID: {user_url}")
            return results
        
        end_page = start_page + pages - 1
        print(f"准备在用户 {user_id} 的主页中搜索关键词 '{keyword}', 计划爬取 {start_page} 到 {end_page} 页")
        
        for page in range(start_page, end_page + 1):
            try:
                print(f"正在爬取第 {page} 页...")
                
                # 构建API URL
                api_url = f"https://weibo.com/ajax/statuses/mymblog?uid={user_id}&page={page}"
                
                # 发送请求
                self._update_headers()
                response = requests.get(api_url, headers=self.headers, cookies=self.cookies)
                
                if response.status_code != 200:
                    print(f"页面 {page} 请求失败: {response.status_code}")
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
                        
                        # 检查是否包含关键词（不区分大小写）
                        if keyword.lower() not in content.lower():
                            continue
                            
                        weibo_data = {
                            'weibo_id': weibo.get('id', '未知ID'),
                            'user_id': user_id,
                            'content': content,
                            'publish_time': weibo.get('created_at', '未知时间'),
                            'reposts_count': weibo.get('reposts_count', 0),
                            'comments_count': weibo.get('comments_count', 0),
                            'attitudes_count': weibo.get('attitudes_count', 0),
                            'source': weibo.get('source', '未知来源'),
                            'keyword': keyword  # 添加匹配的关键词
                        }
                        
                        # 检查是否包含视频
                        has_video = False
                        video_url = ''
                        video_cover = ''
                        
                        # 检查page_info中的视频信息
                        page_info = weibo.get('page_info', {})
                        if page_info and page_info.get('type') == 'video':
                            has_video = True
                            media_info = page_info.get('media_info', {})
                            video_url = media_info.get('mp4_720p_mp4', '') or media_info.get('mp4_hd_url', '') or media_info.get('mp4_sd_url', '')
                            video_cover = page_info.get('page_pic', {}).get('url', '')
                        
                        # 检查混合媒体中的视频
                        mix_media_info = weibo.get('mix_media_info', {})
                        media_items = mix_media_info.get('items', [])
                        for item in media_items:
                            if item.get('type') == 'video':
                                has_video = True
                                media_info = item.get('data', {}).get('media_info', {})
                                if not video_url:  # 如果之前没有找到视频URL
                                    video_url = media_info.get('mp4_720p_mp4', '') or media_info.get('mp4_hd_url', '') or media_info.get('mp4_sd_url', '')
                                if not video_cover:  # 如果之前没有找到封面图
                                    video_cover = item.get('data', {}).get('thumb_pic', '')
                        
                        weibo_data['has_video'] = has_video
                        weibo_data['video_url'] = video_url
                        weibo_data['video_cover'] = video_cover
                        
                        # 检查是否已经爬取过这条微博
                        if weibo_data['weibo_id'] not in self.seen_weibos:
                            self.seen_weibos.add(weibo_data['weibo_id'])
                            results.append(weibo_data)
                            print(f"找到匹配关键词 '{keyword}' 的微博: {content[:50]}...")
                            if has_video:
                                print(f"该微博包含视频，封面图: {video_cover}")
                
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
    
    def crawl_user_profile(self, user_url, max_pages=5):
        """
        爬取用户主页的微博内容
        
        参数:
        - user_url: 用户主页URL
        - max_pages: 最大爬取页数
        
        返回:
        - 用户微博列表
        """
        results = []
        user_id = self._extract_user_id(user_url)
        if not user_id:
            print(f"无法从URL中提取用户ID: {user_url}")
            return results

        print(f"开始爬取用户 {user_id} 的微博")
        
        for page in tqdm(range(1, max_pages + 1), desc="爬取用户微博"):
            try:
                # 构建用户微博列表页URL
                profile_url = f"https://weibo.com/ajax/statuses/mymblog?uid={user_id}&page={page}"
                
                # 更新请求头
                self._update_headers()
                time.sleep(self._get_random_delay())
                
                # 发送请求
                response = requests.get(
                    profile_url,
                    headers=self.headers,
                    cookies=self.cookies,
                    timeout=10
                )
                
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
                        weibo_data = {
                            'weibo_id': weibo.get('id', '未知ID'),
                            'user_id': user_id,
                            'content': weibo.get('text_raw', '无内容'),
                            'publish_time': weibo.get('created_at', '未知时间'),
                            'reposts_count': weibo.get('reposts_count', 0),
                            'comments_count': weibo.get('comments_count', 0),
                            'attitudes_count': weibo.get('attitudes_count', 0),
                            'source': weibo.get('source', '未知来源')
                        }
                        
                        # 提取图片URL
                        pics = weibo.get('pic_ids', [])
                        if pics:
                            weibo_data['image_urls'] = [
                                f"https://wx1.sinaimg.cn/large/{pic_id}.jpg"
                                for pic_id in pics
                            ]
                        
                        results.append(weibo_data)
                
                except json.JSONDecodeError:
                    print(f"解析JSON失败，页面 {page}")
                    continue
                
            except Exception as e:
                print(f"爬取页面 {page} 时出错: {str(e)}")
                continue
        
        return results
    
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

    def crawl_users_from_file(self, file_path, max_pages_per_user=5):
        """
        从文件中读取用户URL并爬取每个用户的微博
        
        参数:
        - file_path: 包含用户URL的文件路径
        - max_pages_per_user: 每个用户最多爬取的页数
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                user_urls = [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"读取文件失败: {str(e)}")
            return
        
        print(f"从文件中读取到 {len(user_urls)} 个用户URL")
        
        for i, user_url in enumerate(user_urls, 1):
            print(f"\n处理第 {i}/{len(user_urls)} 个用户: {user_url}")
            
            results = self.crawl_user_profile(user_url, max_pages_per_user)
            
            if results:
                # 保存结果到JSON文件
                user_id = self._extract_user_id(user_url) or f"user_{i}"
                output_file = os.path.join(self.results_dir, f"user_{user_id}_weibos.json")
                
                try:
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(results, f, ensure_ascii=False, indent=2)
                    print(f"已保存用户 {user_id} 的微博数据到 {output_file}")
                except Exception as e:
                    print(f"保存结果失败: {str(e)}")
            
            # 在处理下一个用户之前添加延迟
            if i < len(user_urls):
                delay = self._get_random_delay() * 2
                print(f"等待 {delay:.1f} 秒后继续...")
                time.sleep(delay)

    def set_cookies(self, cookie_str):
        """设置cookies"""
        if not cookie_str:
            return
        
        try:
            # 处理多种cookie格式
            if isinstance(cookie_str, str):
                # 如果是字符串，尝试解析为字典
                if cookie_str.startswith('{'):
                    # JSON格式
                    self.cookies = json.loads(cookie_str)
                else:
                    # Cookie字符串格式
                    self.cookies = dict([item.split("=", 1) for item in cookie_str.split("; ")])
            elif isinstance(cookie_str, dict):
                self.cookies = cookie_str
            else:
                print("不支持的cookie格式")
                return
            
        print("Cookie设置成功")
        except Exception as e:
            print(f"设置Cookie失败: {str(e)}")

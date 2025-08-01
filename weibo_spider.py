#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import json
import time
import random
import os
from datetime import datetime
from ml_analyzer import MLAnalyzer
import re

class WeiboSpider:
    def __init__(self, output_dir="results"):
        """
        初始化微博爬虫
        
        参数:
        - output_dir: 输出目录
        """
        self.output_dir = output_dir
        self.seen_weibos = set()
        self.analyzer = MLAnalyzer()
        
        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # 设置请求头和Cookie
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://weibo.com/',
            'Connection': 'keep-alive',
            'Cookie': 'alf=02_1750516658; scf=AkWHOAHKVZR4U72tMy8Q9LgjIM7MQMvaHKSwQ04eOAsI2JBgQkQlmfrVVyedYcX4H4xf1lMZmepPJVFN3N841Ao.; SUB=_2A25FK0biDeRhGeFN4lcQ9CvOwjiIHXVmScYqrDV8PUNbmtAbLW_WkW9NQ6CKww8EwXECI8JlmiQpUQKXs8dpOdDq; SUBP=0033WrSXqPxfM725Ws9jqgMF55529P9D9WWeLWqEhZspcsieflC20plM5NHD95QNe0.feKBfeo.XWs4DqcjLPEH81F-ReE-RBEH8SCHWxbHF1CH8SFHFBE-4SEH8SE-4SF-4xntt; WBPSESS=W66fnaoZnYKPDz3Z3SHfiobUNR0t11ESD3A9xqxy8ehc3p8TkmgbC7FjmtozMmYK7QurYzSmlE6O2FLDqKVDAqh-oFLsCLR8CxSj2aBAfc71Qt-4PUU6Ve_iJBaTQAnP-qLHPOmuJ13HfRasQnf_zA==; XSRF-TOKEN=QXhEQujwl5E0gIA29udcRdhn'
        }
    
    def _generate_post_link(self, weibo_id):
        """Generate post link from weibo_id"""
        return f"https://weibo.com/detail/{weibo_id}"

    def _process_weibo_data(self, mblog):
        """Process raw weibo data into standardized format"""
        weibo_id = mblog.get('id', '')
        content = mblog.get('text', '')
        
        # 清理内容中的换行符和多余空格
        content = re.sub(r'\s+', ' ', content.strip())
        content = self.analyzer.preprocess_text(content)
        
        return {
            'weibo_id': weibo_id,
            'content': content,
            'publish_time': mblog.get('created_at', ''),
            'reposts_count': mblog.get('reposts_count', 0),
            'comments_count': mblog.get('comments_count', 0),
            'attitudes_count': mblog.get('attitudes_count', 0),
            'post_link': self._generate_post_link(weibo_id)
        }

    def search_keyword(self, user_url, keyword, pages, start_page=1, download_media=False):
        """Search for weibos containing the keyword"""
        results = []
        user_id = self._extract_user_id(user_url)
        
        if not user_id:
            print(f"无法从URL提取用户ID: {user_url}")
            return results
            
        print(f"\n开始搜索用户 {user_id} 的微博，关键词: '{keyword}'")
        print(f"计划爬取 {pages} 页，从第 {start_page} 页开始")
        
        for page in range(start_page, start_page + pages):
            try:
                print(f"\n正在爬取第 {page} 页...")
                response = self._fetch_user_weibos(user_id, page)
                
                if not response:
                    print(f"获取页面 {page} 失败")
                    continue
                
                try:
                    data = response.json()
                    weibo_list = data.get('data', {}).get('list', [])
                    
                    if not weibo_list:
                        print(f"页面 {page} 未找到微博内容，可能已到达末页")
                        break
                    
                    for weibo in weibo_list:
                        content = weibo.get('text_raw', '')
                        
                        if keyword.lower() not in content.lower():
                            continue
                            
                        weibo_data = self._process_weibo_data(weibo)
                        weibo_data['keyword'] = keyword
                        
                        if weibo_data['weibo_id'] not in self.seen_weibos:
                            self.seen_weibos.add(weibo_data['weibo_id'])
                            results.append(weibo_data)
                            print(f"找到匹配关键词 '{keyword}' 的微博: {content[:50]}...")
                
                except json.JSONDecodeError:
                    print(f"解析JSON失败，页面 {page}")
                    continue
                
                time.sleep(self._get_random_delay())
                
            except Exception as e:
                print(f"爬取页面 {page} 时出错: {str(e)}")
                continue
        
        print(f"\n在用户 {user_id} 的主页中共找到 {len(results)} 条包含关键词 '{keyword}' 的微博")
        return results

    def get_entertainment_weibo(self, page=1, count=20):
        """获取娱乐博主的微博"""
        weibo_list = []
        
        for user_id in self.entertainment_users:
            try:
                response = self._fetch_user_weibos(user_id, page, count)
                
                if response and response.status_code == 200:
                    data = response.json()
                    
                    if data.get('ok') == 1:
                        for card in data.get('data', {}).get('cards', []):
                            if card.get('card_type') == 9:  # 微博类型
                                mblog = card.get('mblog', {})
                                weibo_data = self._process_weibo_data(mblog)
                                
                                if weibo_data['weibo_id'] not in self.seen_weibos:
                                    self.seen_weibos.add(weibo_data['weibo_id'])
                                    weibo_list.append(weibo_data)
                
                time.sleep(self._get_random_delay())
                
            except Exception as e:
                print(f"获取用户 {user_id} 的微博时出错: {e}")
                continue
        
        return weibo_list

    def crawl_and_analyze(self, pages=3, min_likes=500):
        """爬取并分析微博"""
        print(f"\n开始爬取微博数据...")
        print(f"计划爬取 {pages} 页，筛选点赞数 ≥ {min_likes} 的微博")
        
        all_weibos = []
        
        # 爬取每个用户的微博
        for page in range(1, pages + 1):
            weibos = self.get_entertainment_weibo(page=page)
            all_weibos.extend(weibos)
            print(f"第 {page} 页: 获取到 {len(weibos)} 条微博")
        
        print(f"\n共获取到 {len(all_weibos)} 条微博")
        
        # 使用机器学习分析器分析微博
        analysis_result = self.analyzer.analyze_weibos(all_weibos, min_likes=min_likes)
        
        # 保存结果
        self._save_result(analysis_result)
        
        return analysis_result
    
    def _save_result(self, result):
        """保存分析结果"""
        if not result:
            return
        
        try:
            # 生成文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = os.path.join(self.output_dir, f'weibo_analysis_{timestamp}.json')
            
            # 创建可序列化的副本
            result_copy = result.copy()
            
            # 处理所有微博数据
            def process_weibo(weibo):
                # 移除不需要的字段
                weibo_copy = {k: v for k, v in weibo.items() if k not in ['user_id', 'image_urls', 'local_image_paths']}
                # 确保有post_link
                if 'post_link' not in weibo_copy and 'weibo_id' in weibo_copy:
                    weibo_copy['post_link'] = f"https://weibo.com/detail/{weibo_copy['weibo_id']}"
                return weibo_copy
            
            # 处理filtered_weibos
            if 'filtered_weibos' in result_copy:
                result_copy['filtered_weibos'] = [process_weibo(weibo) for weibo in result_copy['filtered_weibos']]
            
            # 保存为JSON
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result_copy, f, ensure_ascii=False, indent=2)
            
            print(f"分析结果已保存到 {filename}")
            
            # 提取并保存热门微博
            if 'filtered_weibos' in result_copy:
                hot_weibos = result_copy['filtered_weibos']
                
                if hot_weibos:
                    hot_filename = os.path.join(self.output_dir, f'hot_weibos_{timestamp}.json')
                    
                    with open(hot_filename, 'w', encoding='utf-8') as f:
                        json.dump(hot_weibos, f, ensure_ascii=False, indent=2)
                    
                    print(f"热门微博已保存到 {hot_filename}")
        
        except Exception as e:
            print(f"保存结果时出错: {e}")

# 示例用法
if __name__ == "__main__":
    # 初始化爬虫
    spider = WeiboSpider()
    
    # 爬取并分析微博（默认爬取3页，筛选点赞数≥500的微博）
    result = spider.crawl_and_analyze(pages=3, min_likes=500)
    
    # 打印分析结果概览
    if 'error' not in result:
        print("\n分析结果概览:")
        print(f"原始微博数: {result.get('original_count', 0)}")
        print(f"筛选后微博数: {result.get('filtered_count', 0)}")
        
        if 'trending_topics' in result and result['trending_topics']:
            print("\n热门话题:")
            for i, topic in enumerate(result['trending_topics'][:5], 1):
                print(f"{i}. {topic['keyword']} (热度分: {topic['score']:.2f})") 
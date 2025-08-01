#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
from fetch import WeiboSpider
import json
import os

def read_keywords(file_path):
    """读取关键词列表文件"""
    try:
        # 如果文件路径是 "keywords.txt"，改为从 "keyword and classification.txt" 中读取
        if file_path == 'keywords.txt':
            classification_file = "keyword and classification.txt"
            if os.path.exists(classification_file):
                import pandas as pd
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

def main():
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='从用户主页爬取包含关键词的微博')
    parser.add_argument('--pages', type=int, default=5, help='每个用户爬取的页数（默认：5）')
    parser.add_argument('--download-media', action='store_true', help='是否下载图片')
    args = parser.parse_args()

    # 读取关键词列表
    keywords = read_keywords('keywords.txt')
    if not keywords:
        print("未在keywords.txt中找到任何关键词")
        return

    print(f"从keywords.txt中读取到 {len(keywords)} 个关键词")

    # 读取用户URL列表
    try:
        with open('user_urls.txt', 'r', encoding='utf-8') as f:
            # 过滤掉空行和注释行
            user_urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except Exception as e:
        print(f"读取user_urls.txt失败: {str(e)}")
        return

    if not user_urls:
        print("user_urls.txt中没有找到有效的用户URL")
        return

    print(f"从user_urls.txt中读取到 {len(user_urls)} 个用户URL")

    # 创建爬虫实例
    spider = WeiboSpider()

    # 创建结果目录
    os.makedirs('results', exist_ok=True)

    # 处理每个用户
    for i, user_url in enumerate(user_urls, 1):
        print(f"\n处理第 {i}/{len(user_urls)} 个用户: {user_url}")
        user_id = spider._extract_user_id(user_url) or f"user_{i}"
        
        # 为该用户创建一个结果字典，包含所有关键词的结果
        all_results = {}
        
        # 对每个关键词进行搜索
        for keyword in keywords:
            print(f"\n搜索关键词: {keyword}")
            try:
                # 爬取该用户的微博
                results = spider.search_keyword(
                    user_url=user_url,
                    keyword=keyword,
                    pages=args.pages,
                    download_media=args.download_media
                )
                
                if results:
                    all_results[keyword] = results
                    print(f"找到 {len(results)} 条包含关键词 '{keyword}' 的微博")
                else:
                    print(f"未找到包含关键词 '{keyword}' 的微博")
                
            except Exception as e:
                print(f"处理关键词 {keyword} 时出错: {str(e)}")
                continue
        
        # 保存该用户的所有结果
        if all_results:
            output_file = os.path.join('results', f"user_{user_id}_all_keywords.json")
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(all_results, f, ensure_ascii=False, indent=2)
                print(f"\n已保存所有结果到: {output_file}")
            except Exception as e:
                print(f"保存结果失败: {str(e)}")
        else:
            print(f"\n用户 {user_id} 的微博中未找到任何关键词匹配")

if __name__ == '__main__':
    main() 
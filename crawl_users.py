#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
from WeiboSpider import WeiboSpider

def main():
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='从文件中读取微博用户URL并爬取其微博内容')
    parser.add_argument('input_file', help='包含用户URL的文本文件路径')
    parser.add_argument('--max-pages', type=int, default=5, help='每个用户最多爬取的页数（默认：5）')
    parser.add_argument('--cookie', help='Cookie字符串或JSON（可选）')
    args = parser.parse_args()

    # 创建爬虫实例
    spider = WeiboSpider()
    
    # 如果提供了cookie，设置它
    if args.cookie:
        spider.set_cookies(args.cookie)
    
    # 开始爬取
    spider.crawl_users_from_file(args.input_file, args.max_pages)

if __name__ == '__main__':
    main() 
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import argparse
from hot_content_analyzer import HotContentAnalyzer

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='根据关键词筛选最热门、最有吸引力的微博内容')
    parser.add_argument('keyword', help='要查找的关键词')
    parser.add_argument('--min-score', type=int, default=60, help='最低质量分数阈值，默认60')
    parser.add_argument('--top-n', type=int, default=10, help='返回结果数量，默认10')
    parser.add_argument('--all-files', action='store_true', help='分析所有匹配的文件，而不仅是最新的')
    parser.add_argument('--input-file', help='指定输入文件，而不是从results目录搜索')
    parser.add_argument('--output-file', help='指定输出文件名')
    parser.add_argument('--result-dir', default='results', help='结果目录，默认为results')
    return parser.parse_args()

def main():
    """主函数"""
    args = parse_args()
    
    # 创建分析器
    analyzer = HotContentAnalyzer(result_dir=args.result_dir)
    
    # 确定要分析的数据
    if args.input_file:
        # 如果指定了输入文件，直接加载
        if not os.path.exists(args.input_file):
            print(f"错误: 指定的输入文件 {args.input_file} 不存在")
            return
        
        weibo_data = analyzer.load_csv_data(args.input_file)
        if not weibo_data:
            print("错误: 无法从指定文件加载数据")
            return
    else:
        # 否则，执行分析过程
        result = analyzer.analyze_all_results(args.keyword, not args.all_files)
        if not result:
            print(f"未找到与关键词 '{args.keyword}' 相关的数据")
            return
        
        # 从分析结果中提取全部微博数据
        weibo_data = []
        for cluster in result.get('topic_clusters', {}).values():
            weibo_data.extend(cluster.get('weibos', []))
        
        # 如果没有找到数据，尝试使用appealing_content
        if not weibo_data and 'appealing_content' in result:
            weibo_data = result['appealing_content']
    
    # 打印初始数据统计
    print(f"找到 {len(weibo_data)} 条微博数据")
    
    # 筛选包含关键词的微博
    keyword_weibos = []
    for weibo in weibo_data:
        content = weibo.get('content', '').lower()
        # 如果微博内容包含关键词
        if args.keyword.lower() in content:
            # 确保每条微博都有post_link
            if 'post_link' not in weibo and 'weibo_id' in weibo:
                weibo['post_link'] = f"https://weibo.com/detail/{weibo['weibo_id']}"
            # 移除不需要的字段
            for field in ['user_id', 'image_urls', 'local_image_paths']:
                weibo.pop(field, None)
            keyword_weibos.append(weibo)
    
    print(f"其中 {len(keyword_weibos)} 条微博包含关键词 '{args.keyword}'")
    
    if not keyword_weibos:
        print("没有找到匹配的微博")
        return
    
    # 计算内容分数
    for weibo in keyword_weibos:
        # 如果还没有计算过内容分数
        if 'content_score' not in weibo:
            weibo['content_score'] = analyzer.ml_analyzer.calculate_content_score(weibo)
    
    # 按内容分数过滤
    appealing_weibos = [w for w in keyword_weibos if w.get('content_score', 0) >= args.min_score]
    print(f"经过质量分数过滤(>={args.min_score})，保留 {len(appealing_weibos)} 条高质量微博")
    
    if not appealing_weibos:
        print(f"没有找到质量分数>={args.min_score}的微博，降低分数阈值再试")
        return
    
    # 按内容分数排序
    appealing_weibos.sort(key=lambda x: x.get('content_score', 0), reverse=True)
    
    # 取前top_n个
    top_weibos = appealing_weibos[:args.top_n]
    
    # 准备结果数据
    result = {
        'keyword': args.keyword,
        'total_weibos': len(weibo_data),
        'matching_weibos': len(keyword_weibos),
        'quality_weibos': len(appealing_weibos),
        'top_results': top_weibos
    }
    
    # 导出结果
    output_file = args.output_file
    if not output_file:
        timestamp = analyzer.ml_analyzer.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"{args.result_dir}/hot_{args.keyword}_{timestamp}.csv"
    
    # 将结果导出为CSV
    import pandas as pd
    df = pd.DataFrame(top_weibos)
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"已将{len(top_weibos)}条最热门内容导出到: {output_file}")
    
    # 输出分析结果
    print("\n===== 最热门内容列表 =====")
    for i, weibo in enumerate(top_weibos, 1):
        text = weibo.get('content', '').replace('\n', ' ')
        print(f"\n{i}. 质量分数: {weibo.get('content_score', 0):.1f}")
        print(f"内容: {text[:100]}{'...' if len(text) > 100 else ''}")
        print(f"互动数据: 转发{weibo.get('reposts_count', 0)}, 评论{weibo.get('comments_count', 0)}, 点赞{weibo.get('attitudes_count', 0)}")
        print(f"链接: {weibo.get('post_link', '无')}")

if __name__ == "__main__":
    main() 
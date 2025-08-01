#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import json
import pandas as pd
from datetime import datetime
import glob
from ml_analyzer import MLAnalyzer

class HotContentAnalyzer:
    """热门内容和话题分析器"""
    
    def __init__(self, result_dir="results", model_dir="models"):
        """
        初始化热门内容分析器
        
        参数:
        - result_dir: 结果目录
        - model_dir: 模型目录
        """
        self.result_dir = result_dir
        self.ml_analyzer = MLAnalyzer(model_dir=model_dir)
        
        # 检查结果目录是否存在
        if not os.path.exists(result_dir):
            print(f"结果目录 {result_dir} 不存在，将创建此目录")
            os.makedirs(result_dir, exist_ok=True)
    
    def load_csv_data(self, csv_file):
        """
        加载CSV文件中的微博数据
        
        参数:
        - csv_file: CSV文件路径
        
        返回:
        - 微博数据列表
        """
        try:
            df = pd.read_csv(csv_file, encoding='utf-8-sig')
            # Remove unwanted columns if they exist
            columns_to_drop = ['user_id', 'image_urls', 'local_image_paths']
            df = df.drop(columns=[col for col in columns_to_drop if col in df.columns])
            
            # Add post_link column if it doesn't exist
            if 'post_link' not in df.columns:
                df['post_link'] = df['weibo_id'].apply(lambda x: f"https://weibo.com/detail/{x}")
            
            print(f"已加载 {len(df)} 条微博数据，来自 {csv_file}")
            return df.to_dict('records')
        except Exception as e:
            print(f"加载数据文件 {csv_file} 时出错: {e}")
            return []
    
    def extract_hot_topics(self, weibo_data, top_n=10, min_weibo_count=2):
        """
        从微博数据中提取热门话题
        
        参数:
        - weibo_data: 微博数据列表
        - top_n: 返回的热门话题数量
        - min_weibo_count: 最小相关微博数量
        
        返回:
        - 热门话题列表
        """
        if not weibo_data:
            print("没有提供微博数据")
            return []
        
        # 预处理数据
        for item in weibo_data:
            item['content'] = self.ml_analyzer.preprocess_text(item.get('content', ''))
        
        # 使用机器学习分析器提取热门话题
        trending_topics = self.ml_analyzer.identify_trending_topics(weibo_data, top_n=top_n*2)
        
        # 过滤掉相关微博数量过少的话题
        filtered_topics = [topic for topic in trending_topics if topic['weibo_count'] >= min_weibo_count]
        
        # 返回前top_n个话题
        return filtered_topics[:top_n]
    
    def find_appealing_content(self, weibo_data, top_n=20, min_score=70):
        """
        从微博数据中找出最有吸引力的内容
        
        参数:
        - weibo_data: 微博数据列表
        - top_n: 返回的内容数量
        - min_score: 最低质量分数阈值
        
        返回:
        - 最有吸引力的内容列表
        """
        if not weibo_data:
            print("没有提供微博数据")
            return []
        
        # 预处理数据并计算内容分数
        for item in weibo_data:
            item['content'] = self.ml_analyzer.preprocess_text(item.get('content', ''))
            item['content_score'] = self.ml_analyzer.calculate_content_score(item)
        
        # 按内容分数过滤
        appealing_content = [item for item in weibo_data if item.get('content_score', 0) >= min_score]
        
        # 按内容分数排序
        appealing_content.sort(key=lambda x: x.get('content_score', 0), reverse=True)
        
        # 取前top_n个
        return appealing_content[:top_n]
    
    def cluster_by_topic(self, weibo_data, n_clusters=5):
        """
        按话题聚类微博内容
        
        参数:
        - weibo_data: 微博数据列表
        - n_clusters: 聚类数量
        
        返回:
        - 聚类结果字典，格式为 {聚类ID: {关键词列表, 微博列表}}
        """
        if not weibo_data:
            print("没有提供微博数据")
            return {}
        
        # 预处理数据
        for item in weibo_data:
            item['content'] = self.ml_analyzer.preprocess_text(item.get('content', ''))
        
        # 执行聚类
        cluster_labels, cluster_keywords = self.ml_analyzer.cluster_topics(weibo_data, n_clusters)
        
        # 按聚类组织结果
        clusters = {}
        for i, label in enumerate(cluster_labels):
            if label not in clusters:
                clusters[label] = {
                    'keywords': cluster_keywords.get(label, []),
                    'weibos': []
                }
            clusters[label]['weibos'].append(weibo_data[i])
        
        return clusters
    
    def analyze_all_results(self, keyword=None, latest_only=True):
        """
        分析结果目录中的所有CSV文件
        
        参数:
        - keyword: 特定关键词，如果提供则只分析该关键词的结果
        - latest_only: 是否只分析最新的结果文件
        
        返回:
        - 分析结果字典
        """
        # 构建文件匹配模式
        if keyword:
            file_pattern = f"{self.result_dir}/{keyword}_*.csv"
        else:
            file_pattern = f"{self.result_dir}/*.csv"
        
        # 获取所有匹配的文件
        csv_files = glob.glob(file_pattern)
        
        # 按修改时间排序
        csv_files.sort(key=os.path.getmtime, reverse=True)
        
        # 如果指定只分析最新文件，且找到了文件
        if latest_only and csv_files:
            # 去掉带有"filtered"和"all_results"的文件
            original_files = [f for f in csv_files if "filtered" not in f and "all_results" not in f]
            if original_files:
                csv_files = [original_files[0]]
            else:
                csv_files = [csv_files[0]]
        
        if not csv_files:
            print(f"未找到匹配的CSV文件: {file_pattern}")
            return None
        
        # 加载并合并所有数据
        all_data = []
        for csv_file in csv_files:
            data = self.load_csv_data(csv_file)
            all_data.extend(data)
        
        if not all_data:
            print("没有找到微博数据")
            return None
        
        print(f"\n共分析 {len(all_data)} 条微博数据")
        
        # 执行分析
        # 1. 提取热门话题
        hot_topics = self.extract_hot_topics(all_data)
        
        # 2. 找出最有吸引力的内容
        appealing_content = self.find_appealing_content(all_data)
        
        # 3. 按话题聚类
        topic_clusters = self.cluster_by_topic(all_data)
        
        # 构建分析结果
        result = {
            'total_weibos': len(all_data),
            'hot_topics': hot_topics,
            'appealing_content': appealing_content,
            'topic_clusters': topic_clusters
        }
        
        return result
    
    def save_analysis_result(self, result, output_file=None):
        """
        保存分析结果
        
        参数:
        - result: 分析结果
        - output_file: 输出文件名，如果不提供则自动生成
        
        返回:
        - 保存的文件路径
        """
        if not result:
            print("没有分析结果可保存")
            return None
        
        # 如果没有提供输出文件名，自动生成
        if not output_file:
            now = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"{self.result_dir}/hot_analysis_{now}.json"
        
        # 创建可序列化的副本
        result_copy = result.copy()
        
        # 处理appealing_content字段
        if 'appealing_content' in result_copy:
            serializable_content = []
            for item in result_copy['appealing_content']:
                item_copy = {k: v for k, v in item.items() if k not in ['user_id', 'image_urls', 'local_image_paths']}
                if 'post_link' not in item_copy and 'weibo_id' in item_copy:
                    item_copy['post_link'] = f"https://weibo.com/detail/{item_copy['weibo_id']}"
                serializable_content.append(item_copy)
            result_copy['appealing_content'] = serializable_content
        
        # 处理topic_clusters字段
        if 'topic_clusters' in result_copy:
            serializable_clusters = {}
            for cluster_id, cluster_data in result_copy['topic_clusters'].items():
                weibos = []
                for weibo in cluster_data.get('weibos', []):
                    weibo_copy = {k: v for k, v in weibo.items() if k not in ['user_id', 'image_urls', 'local_image_paths']}
                    if 'post_link' not in weibo_copy and 'weibo_id' in weibo_copy:
                        weibo_copy['post_link'] = f"https://weibo.com/detail/{weibo_copy['weibo_id']}"
                    weibos.append(weibo_copy)
                
                serializable_clusters[str(cluster_id)] = {
                    'keywords': cluster_data.get('keywords', []),
                    'weibos': weibos
                }
            result_copy['topic_clusters'] = serializable_clusters
        
        # 保存为JSON
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result_copy, f, ensure_ascii=False, indent=2)
            print(f"分析结果已保存到: {output_file}")
            return output_file
        except Exception as e:
            print(f"保存分析结果时出错: {e}")
            return None
    
    def generate_hot_topics_report(self, result, output_file=None):
        """
        生成热门话题报告
        
        参数:
        - result: 分析结果
        - output_file: 输出文件名，如果不提供则自动生成
        
        返回:
        - 保存的文件路径
        """
        if not result or 'hot_topics' not in result or not result['hot_topics']:
            print("没有热门话题可报告")
            return None
        
        # 如果没有提供输出文件名，自动生成
        if not output_file:
            now = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"{self.result_dir}/hot_topics_report_{now}.txt"
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("===== 微博热门话题分析报告 =====\n\n")
                f.write(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"分析微博总数: {result.get('total_weibos', 0)} 条\n\n")
                
                f.write("==== 热门话题排名 ====\n\n")
                for i, topic in enumerate(result['hot_topics'], 1):
                    f.write(f"{i}. {topic['keyword']}\n")
                    f.write(f"   热度分数: {topic['score']:.2f}\n")
                    f.write(f"   相关微博数: {topic['weibo_count']} 条\n")
                    f.write(f"   平均转发: {topic['avg_forwards']:.1f}, 评论: {topic['avg_comments']:.1f}, 点赞: {topic['avg_likes']:.1f}\n")
                    f.write("\n")
                
                f.write("\n==== 话题聚类分析 ====\n\n")
                for cluster_id, cluster_data in result.get('topic_clusters', {}).items():
                    keywords = cluster_data.get('keywords', [])
                    weibos = cluster_data.get('weibos', [])
                    if not keywords or not weibos:
                        continue
                    
                    f.write(f"话题组 {cluster_id}: {', '.join(keywords)}\n")
                    f.write(f"包含 {len(weibos)} 条微博\n\n")
                
                f.write("\n==== 最有吸引力的内容Top5 ====\n\n")
                for i, content in enumerate(result.get('appealing_content', [])[:5], 1):
                    f.write(f"{i}. 内容评分: {content.get('content_score', 0):.1f}\n")
                    f.write(f"   用户: {content.get('user_name', '未知')}\n")
                    text = content.get('content', '').replace('\n', ' ')
                    f.write(f"   内容: {text[:100]}{'...' if len(text) > 100 else ''}\n")
                    f.write(f"   互动数据: 转发 {content.get('forwards', 0)}, 评论 {content.get('comments', 0)}, 点赞 {content.get('likes', 0)}\n")
                    f.write(f"   链接: {content.get('post_link', '无')}\n")
                    f.write("\n")
            
            print(f"热门话题报告已生成: {output_file}")
            return output_file
        except Exception as e:
            print(f"生成热门话题报告时出错: {e}")
            return None
    
    def export_appealing_content(self, result, output_file=None):
        """
        导出最有吸引力的内容到CSV
        
        参数:
        - result: 分析结果
        - output_file: 输出文件名，如果不提供则自动生成
        
        返回:
        - 保存的文件路径
        """
        if not result or 'appealing_content' not in result or not result['appealing_content']:
            print("没有吸引力内容可导出")
            return None
        
        # 如果没有提供输出文件名，自动生成
        if not output_file:
            now = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"{self.result_dir}/appealing_content_{now}.csv"
        
        try:
            # 转换为DataFrame
            df = pd.DataFrame(result['appealing_content'])
            
            # 导出到CSV
            df.to_csv(output_file, index=False, encoding='utf-8-sig')
            print(f"最有吸引力的内容已导出到: {output_file}")
            return output_file
        except Exception as e:
            print(f"导出最有吸引力的内容时出错: {e}")
            return None

def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python hot_content_analyzer.py <关键词> [--all-files]")
        print("如果不提供关键词，将分析所有结果")
        keyword = None
        latest_only = True
    else:
        keyword = sys.argv[1]
        latest_only = "--all-files" not in sys.argv
    
    # 创建分析器
    analyzer = HotContentAnalyzer()
    
    # 执行分析
    print(f"开始分析{'所有' if not keyword else keyword}微博数据...")
    print(f"{'只分析最新文件' if latest_only else '分析所有匹配文件'}")
    
    # 分析结果
    result = analyzer.analyze_all_results(keyword, latest_only)
    
    if not result:
        print("分析失败，未找到数据或分析过程出错")
        return
    
    # 保存分析结果
    analyzer.save_analysis_result(result)
    
    # 生成热门话题报告
    analyzer.generate_hot_topics_report(result)
    
    # 导出最有吸引力的内容
    analyzer.export_appealing_content(result)
    
    # 打印热门话题
    if result.get('hot_topics'):
        print("\n===== 热门话题 =====")
        for i, topic in enumerate(result['hot_topics'][:10], 1):
            print(f"{i}. {topic['keyword']} (热度分数: {topic['score']:.2f}, 相关微博: {topic['weibo_count']}条)")
    
    # 打印最有吸引力的内容
    if result.get('appealing_content'):
        print("\n===== 最有吸引力的内容 Top 5 =====")
        for i, content in enumerate(result['appealing_content'][:5], 1):
            text = content.get('content', '').replace('\n', ' ')
            print(f"{i}. [{content.get('content_score', 0):.1f}分] {text[:50]}{'...' if len(text) > 50 else ''}")
            print(f"   - 用户: {content.get('user_name', '未知')}, 互动: 转发{content.get('forwards', 0)}, 评论{content.get('comments', 0)}, 点赞{content.get('likes', 0)}")
            print(f"   - 链接: {content.get('post_link', '无')}")

if __name__ == "__main__":
    main() 
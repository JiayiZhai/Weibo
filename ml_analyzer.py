#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import joblib
import xgboost as xgb
from collections import Counter
import jieba
import jieba.analyse
import re
import warnings
warnings.filterwarnings('ignore')

class MLAnalyzer:
    def __init__(self, model_dir="models"):
        """
        初始化机器学习分析器
        
        参数:
        - model_dir: 模型保存目录
        """
        self.model_dir = model_dir
        os.makedirs(model_dir, exist_ok=True)
        
        # 加载中文停用词
        self.stopwords = self._load_stopwords()
        
        # 初始化XGBoost模型用于内容评分
        try:
            self.xgb_model = self._load_or_create_xgb_model()
            print("XGBoost模型初始化成功")
        except Exception as e:
            print(f"XGBoost模型初始化失败: {e}")
            print("将使用简化评分逻辑")
            self.xgb_model = None
        
        # TF-IDF向量化器，用于主题建模
        self.vectorizer = TfidfVectorizer(max_features=5000, stop_words=self.stopwords)
        
        # 聚类模型，用于话题聚类
        self.kmeans = None
        
        # 加载jieba自定义词典
        self._load_custom_dict()
        
        print("分析器初始化完成 - 优化版（无BERT依赖）")
    
    def _load_stopwords(self):
        """加载中文停用词"""
        try:
            stopwords_file = os.path.join(self.model_dir, "stopwords.txt")
            
            # 如果停用词文件不存在，创建一个基础版本
            if not os.path.exists(stopwords_file):
                basic_stopwords = ["的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", 
                                   "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", 
                                   "着", "没有", "看", "好", "自己", "这"]
                with open(stopwords_file, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(basic_stopwords))
            
            with open(stopwords_file, 'r', encoding='utf-8') as f:
                stopwords = [line.strip() for line in f.readlines()]
            return stopwords
        except Exception as e:
            print(f"加载停用词时出错: {e}")
            return []
    
    def _load_custom_dict(self):
        """加载自定义词典到jieba"""
        try:
            # 添加热门领域的关键词
            custom_words = [
                "人工智能", "机器学习", "深度学习", "神经网络", "自然语言处理", 
                "数字化转型", "元宇宙", "区块链", "大数据", "云计算",
                "碳中和", "碳达峰", "绿色能源", "可持续发展", 
                "乡村振兴", "精准扶贫", "脱贫攻坚",
                # 添加娱乐相关词汇
                "明星", "综艺", "电影", "电视剧", "演员", "导演", "歌手",
                "音乐", "演唱会", "热搜", "八卦", "绯闻", "爆料", "票房",
                "收视率", "网红", "直播", "短视频", "剧情", "粉丝", "流量"
            ]
            
            custom_dict_file = os.path.join(self.model_dir, "custom_dict.txt")
            with open(custom_dict_file, 'w', encoding='utf-8') as f:
                for word in custom_words:
                    f.write(f"{word} 5\n")  # 词 权重
            
            jieba.load_userdict(custom_dict_file)
        except Exception as e:
            print(f"加载自定义词典时出错: {e}")
    
    def _load_or_create_xgb_model(self):
        """加载或创建XGBoost模型"""
        xgb_model_path = os.path.join(self.model_dir, "xgboost_content_scorer.model")
        
        if os.path.exists(xgb_model_path):
            print("从本地加载XGBoost模型...")
            return xgb.Booster(model_file=xgb_model_path)
        else:
            print("创建新的XGBoost模型...")
            # 创建一个基础的XGBoost模型
            params = {
                'objective': 'reg:squarederror',
                'max_depth': 5,
                'eta': 0.1,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'eval_metric': 'rmse'
            }
            
            # 创建空模型
            model = xgb.Booster(params)
            
            # 保存模型
            model.save_model(xgb_model_path)
            return model
    
    def preprocess_text(self, text):
        """
        预处理文本内容
        
        参数:
        - text: 原始文本
        
        返回:
        - 处理后的文本
        """
        if not text:
            return ""
            
        try:
            # 转换为字符串
            text = str(text)
            
            # 移除HTML标签
            text = re.sub(r'<[^>]+>', '', text)
            
            # 移除URL
            text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
            
            # 移除表情符号和特殊字符
            text = re.sub(r'[\U0001F300-\U0001F9FF]', '', text)
            
            # 移除所有换行符和多余的空格
            text = re.sub(r'\s+', ' ', text)
            
            # 移除首尾空格
            text = text.strip()
            
            return text
            
        except Exception as e:
            print(f"预处理文本时出错: {e}")
        
        # 去除HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        
        # 去除URL
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        
        # 去除@用户
        text = re.sub(r'@[\w\-]+', '', text)
        
        # 去除话题标签 #xxx#
        text = re.sub(r'#([^#]+)#', r'\1', text)
        
        # 去除表情符号
        emoji_pattern = re.compile("["
                               u"\U0001F600-\U0001F64F"  # emoticons
                               u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                               u"\U0001F680-\U0001F6FF"  # transport & map symbols
                               u"\U0001F700-\U0001F77F"  # alchemical symbols
                               u"\U0001F780-\U0001F7FF"  # Geometric Shapes
                               u"\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
                               u"\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
                               u"\U0001FA00-\U0001FA6F"  # Chess Symbols
                               u"\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
                               u"\U00002702-\U000027B0"  # Dingbats
                               "]+", flags=re.UNICODE)
        text = emoji_pattern.sub(r'', text)
        
        # 去除多余的空格
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def extract_keywords(self, text, topk=10):
        """
        从文本中提取关键词
        
        参数:
        - text: 待处理的文本
        - topk: 返回的关键词数量
        
        返回:
        - 关键词列表和权重
        """
        if not text:
            return [], []
        
        # 使用jieba提取关键词
        keywords = jieba.analyse.extract_tags(text, topK=topk, withWeight=True)
        return [k[0] for k in keywords], [k[1] for k in keywords]
    
    def get_simple_sentiment(self, text):
        """
        使用简单关键词匹配进行情感分析（替代BERT情感分析）
        
        参数:
        - text: 待分析的文本
        
        返回:
        - 情感极性 (positive, negative, neutral) 和置信度
        """
        if not text or len(text) < 5:
            return {"label": "neutral", "score": 0.5}
        
        try:
            # 基于关键词的简单情感分析
            positive_words = ["好", "赞", "棒", "喜欢", "支持", "感谢", "厉害", "牛", "优秀", "不错"]
            negative_words = ["差", "烂", "坏", "讨厌", "失望", "可惜", "遗憾", "问题", "垃圾", "骗"]
            
            pos_count = sum(1 for word in positive_words if word in text)
            neg_count = sum(1 for word in negative_words if word in text)
            
            total = pos_count + neg_count
            if total == 0:
                return {"label": "neutral", "score": 0.5}
            
            if pos_count > neg_count:
                score = pos_count / (pos_count + neg_count)
                return {"label": "positive", "score": score}
            else:
                score = neg_count / (pos_count + neg_count)
                return {"label": "negative", "score": score}
        except Exception as e:
            print(f"情感分析出错: {e}")
            return {"label": "neutral", "score": 0.5}
    
    def calculate_content_score(self, weibo_data):
        """
        计算微博内容的综合分数
        
        参数:
        - weibo_data: 微博数据字典
        
        返回:
        - 内容分数 (0-100)
        """
        try:
            # 获取互动数据
            likes = float(weibo_data.get('likes', 0))
            forwards = float(weibo_data.get('forwards', 0))
            comments = float(weibo_data.get('comments', 0))
            
            # 对所有点赞数≥500的微博进行综合评分
            
            # 1. 互动影响力分数 (0-60分) - 提高权重
            # 目的：评估内容的社交影响力和传播能力
            # 转发和点赞同等重要，分别表示内容的传播价值和认可度
            # 评论表示内容引发讨论和参与度
            interaction_score = min(60, (forwards * 0.4 + likes * 0.4 + comments * 0.2) / 100)
            
            # 2. 媒体吸引力分数 (0-15分) - 提高权重
            # 目的：评估内容的视觉吸引力和多媒体丰富度
            # 视频和图片内容更具吸引力，更容易获得关注
            has_images = weibo_data.get('has_images', False)
            has_videos = weibo_data.get('has_videos', False)
            media_score = 15 if has_videos else (10 if has_images else 0)
            
            # 3. 内容长度分数 (0-10分)
            # 目的：评估内容的丰富程度
            # 但内容长度不是质量的决定性因素，所以权重较低
            content = weibo_data.get('content', '')
            content_len = len(content) if content else 0
            length_score = min(10, content_len / 20)
            
            # 4. 话题相关性分数 (0-15分) - 代替情感分析
            # 目的：评估内容与热门话题的相关程度和关键词质量
            # 通过jieba提取关键词，判断内容的话题相关性
            try:
                keywords, weights = self.extract_keywords(content, topk=8)
                # 关键词权重总和越高，表示内容越聚焦于重要话题
                keyword_score = min(15, sum(weights) * 15) if weights else 0
            except Exception as e:
                print(f"关键词提取出错: {e}")
                keyword_score = 0
            
            # 5. 情感分析分数 (0-0分) - 移除情感分析的影响
            # 影响力和吸引力与情感倾向关系不大，所以不再使用情感分析评分
            sentiment_score = 0
            
            # 计算总分 - 总计100分
            base_score = interaction_score + media_score + length_score + keyword_score + sentiment_score
            
            # 归一化到0-100
            final_score = min(100, base_score)
            
            return final_score
            
        except Exception as e:
            print(f"计算内容分数时出错: {e}")
            # 如果出现错误，使用简单的基于互动数据的评分
            try:
                likes = float(weibo_data.get('likes', 0))
                forwards = float(weibo_data.get('forwards', 0))
                comments = float(weibo_data.get('comments', 0))
                
                # 简单评分：转发*0.4 + 点赞*0.4 + 评论*0.2，上限100分
                simple_score = min(100, (forwards * 0.4 + likes * 0.4 + comments * 0.2) / 100)
                return simple_score
            except:
                return 50  # 默认中等分数
    
    def cluster_topics(self, weibo_list, n_clusters=5):
        """
        对微博内容进行话题聚类
        
        参数:
        - weibo_list: 微博数据列表
        - n_clusters: 聚类数量
        
        返回:
        - 聚类标签和每个聚类的关键词
        """
        if not weibo_list or len(weibo_list) < n_clusters:
            return [], {}
        
        try:
            # 提取内容
            contents = [self.preprocess_text(item.get('content', '')) for item in weibo_list]
            valid_contents = [c for c in contents if c]
            
            if len(valid_contents) < n_clusters:
                return [], {}
            
            # 向量化
            X = self.vectorizer.fit_transform(valid_contents)
            
            # 聚类
            self.kmeans = KMeans(n_clusters=n_clusters, random_state=42)
            cluster_labels = self.kmeans.fit_predict(X)
            
            # 获取每个聚类的关键词
            cluster_keywords = {}
            feature_names = self.vectorizer.get_feature_names_out()
            
            for i in range(n_clusters):
                # 找出属于该聚类的所有文档索引
                indices = [j for j, label in enumerate(cluster_labels) if label == i]
                
                if not indices:
                    continue
                
                # 收集该聚类中的所有文档
                cluster_docs = [valid_contents[j] for j in indices]
                
                # 提取该聚类的关键词
                all_keywords = []
                for doc in cluster_docs:
                    keywords, _ = self.extract_keywords(doc, topk=5)
                    all_keywords.extend(keywords)
                
                # 统计关键词频率
                keyword_counter = Counter(all_keywords)
                top_keywords = keyword_counter.most_common(5)
                
                cluster_keywords[i] = [kw[0] for kw in top_keywords]
            
            return cluster_labels, cluster_keywords
            
        except Exception as e:
            print(f"聚类分析时出错: {e}")
            return [], {}
    
    def filter_noise(self, weibo_list, min_score=50, min_likes=500, min_comments=0, min_forwards=0):
        """
        过滤低质量内容
        
        参数:
        - weibo_list: 微博数据列表
        - min_score: 最低质量分数阈值（已弃用，保留参数为了兼容性）
        - min_likes: 最低点赞数（默认500）
        - min_comments: 最低评论数（默认0）
        - min_forwards: 最低转发数（默认0）
        
        返回:
        - 过滤后的微博列表
        """
        if not weibo_list:
            return []
        
        filtered_list = []
        for weibo in weibo_list:
            # 1. 进行硬性筛选 - 点赞数、评论数和转发数必须达到要求
            try:
                likes = int(float(weibo.get('likes', 0)))
                comments = int(float(weibo.get('comments', 0)))
                forwards = int(float(weibo.get('forwards', 0)))
            except (ValueError, TypeError):
                likes = 0
                comments = 0
                forwards = 0
                
            if likes < min_likes or comments < min_comments or forwards < min_forwards:
                continue
                
            # 2. 尝试计算内容分数，但如果出错，不影响筛选结果
            try:
                score = self.calculate_content_score(weibo)
                weibo['content_score'] = score
            except Exception as e:
                print(f"计算内容分数时出错: {e}")
                weibo['content_score'] = 50  # 设置默认分数
        
            # 3. 添加到保留列表
            filtered_list.append(weibo)
        
        # 4. 尝试按点赞数和内容分数排序
        try:
            filtered_list.sort(key=lambda x: (float(x.get('likes', 0)), x.get('content_score', 0)), reverse=True)
        except Exception as e:
            print(f"排序时出错: {e}")
            # 至少按点赞数排序
            try:
                filtered_list.sort(key=lambda x: float(x.get('likes', 0)), reverse=True)
            except:
                pass  # 如果还是出错，就保持原始顺序
        
        return filtered_list
    
    def identify_trending_topics(self, weibo_list, top_n=5):
        """
        识别热门话题
        
        参数:
        - weibo_list: 微博数据列表
        - top_n: 返回的热门话题数量
        
        返回:
        - 热门话题列表，每个元素包含关键词和分数
        """
        if not weibo_list:
            return []
        
        try:
            # 提取所有内容
            all_content = " ".join([weibo.get('content', '') for weibo in weibo_list])
            
            # 提取关键词
            keywords, weights = self.extract_keywords(all_content, topk=top_n*2)
            
            # 按照互动数据和内容分数计算每个关键词的热度
            keyword_trends = []
            for keyword in keywords:
                # 找出包含该关键词的所有微博
                related_weibos = [weibo for weibo in weibo_list if keyword in weibo.get('content', '')]
                
                if not related_weibos:
                    continue
                
                # 计算平均互动数据
                avg_forwards = sum(float(weibo.get('forwards', 0)) for weibo in related_weibos) / len(related_weibos)
                avg_comments = sum(float(weibo.get('comments', 0)) for weibo in related_weibos) / len(related_weibos)
                avg_likes = sum(float(weibo.get('likes', 0)) for weibo in related_weibos) / len(related_weibos)
                
                # 计算平均内容分数
                avg_score = sum(weibo.get('content_score', 50) for weibo in related_weibos) / len(related_weibos)
                
                # 计算热度分数 (互动数据权重0.7，内容分数权重0.3)
                trend_score = (avg_forwards * 0.4 + avg_likes * 0.4 + avg_comments * 0.2) * 0.7 + avg_score * 0.3
                
                keyword_trends.append({
                    'keyword': keyword,
                    'score': trend_score,
                    'weibo_count': len(related_weibos),
                    'avg_forwards': avg_forwards,
                    'avg_comments': avg_comments,
                    'avg_likes': avg_likes,
                    'avg_content_score': avg_score
                })
            
            # 按热度分数排序
            keyword_trends.sort(key=lambda x: x['score'], reverse=True)
            
            # 返回前top_n个热门话题
            return keyword_trends[:top_n]
            
        except Exception as e:
            #print(f"识别热门话题时出错: {e}")
            return []
    
    def analyze_weibos(self, weibo_list, min_score=50, min_likes=500, min_comments=0, min_forwards=0, n_clusters=5):
        """
        分析微博列表，执行所有分析步骤
        
        参数:
        - weibo_list: 微博数据列表
        - min_score: 过滤噪声的最低分数阈值
        - min_likes: 最低点赞数
        - min_comments: 最低评论数
        - min_forwards: 最低转发数
        - n_clusters: 聚类数量
        
        返回:
        - 分析结果字典
        """
        if not weibo_list:
            return {"error": "输入数据为空"}
        
        try:
            print(f"开始分析 {len(weibo_list)} 条微博...")
            
            # 1. 数据预处理
            processed_weibos = []
            for weibo in weibo_list:
                # 移除不需要的字段
                weibo_copy = {k: v for k, v in weibo.items() 
                            if k not in ['user_id', 'image_urls', 'local_image_paths', 'source']}
                
                # 确保有post_link
                if 'post_link' not in weibo_copy and 'weibo_id' in weibo_copy:
                    weibo_copy['post_link'] = f"https://weibo.com/detail/{weibo_copy['weibo_id']}"
                
                # 预处理文本内容
                if 'content' in weibo_copy:
                    weibo_copy['content'] = self.preprocess_text(weibo_copy['content'])
                
                processed_weibos.append(weibo_copy)
            
            # 2. 过滤噪声
            filtered_weibos = []
            for weibo in processed_weibos:
                if (int(weibo.get('attitudes_count', 0)) >= min_likes and
                    int(weibo.get('comments_count', 0)) >= min_comments and
                    int(weibo.get('reposts_count', 0)) >= min_forwards):
                    filtered_weibos.append(weibo)
            
            print(f"过滤后保留 {len(filtered_weibos)} 条有价值内容")
            print(f"筛选条件: 点赞数 >= {min_likes}, 评论数 >= {min_comments}, 转发数 >= {min_forwards}")
            
            # 3. 话题聚类
            cluster_labels, cluster_keywords = self.cluster_topics(filtered_weibos, n_clusters)
            
            # 4. 识别热门话题
            trending_topics = self.identify_trending_topics(filtered_weibos)
            
            # 返回分析结果
            result = {
                "original_count": len(weibo_list),
                "filtered_count": len(filtered_weibos),
                "filtered_weibos": filtered_weibos,
                "cluster_keywords": cluster_keywords,
                "trending_topics": trending_topics,
                "filter_criteria": {
                    "min_likes": min_likes,
                    "min_comments": min_comments,
                    "min_forwards": min_forwards
                }
            }
            
            return result
        
        except Exception as e:
            print(f"分析微博时出错: {e}")
            return {"error": str(e)}
    
    def update_model_with_feedback(self, weibo_data, user_score):
        """
        根据用户反馈更新模型，实现持续学习
        
        参数:
        - weibo_data: 微博数据
        - user_score: 用户给出的分数 (0-100)
        """
        # 这里可以实现模型更新逻辑
        # 目前为简化版，实际应用中可以收集这些反馈数据再定期训练模型
        print(f"收到用户反馈，微博ID: {weibo_data.get('weibo_id')}, 用户评分: {user_score}")
        
        # 记录反馈数据，用于后续模型更新
        feedback_file = os.path.join(self.model_dir, "user_feedback.csv")
        
        # 提取特征
        content = weibo_data.get('content', '')
        keywords, _ = self.extract_keywords(content, topk=5)
        
        feedback_data = {
            'weibo_id': weibo_data.get('weibo_id', ''),
            'content': content,
            'keywords': '|'.join(keywords),
            'forwards': weibo_data.get('forwards', 0),
            'comments': weibo_data.get('comments', 0),
            'likes': weibo_data.get('likes', 0),
            'has_images': weibo_data.get('has_images', False),
            'has_videos': weibo_data.get('has_videos', False),
            'system_score': weibo_data.get('content_score', 0),
            'user_score': user_score,
            'feedback_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 保存反馈数据
        df = pd.DataFrame([feedback_data])
        
        if os.path.exists(feedback_file):
            df.to_csv(feedback_file, mode='a', header=False, index=False)
        else:
            df.to_csv(feedback_file, index=False)
        
        print(f"反馈数据已保存到 {feedback_file}")
        
        # 如果累积了足够的反馈数据，可以触发模型更新
        if os.path.exists(feedback_file):
            feedback_df = pd.read_csv(feedback_file)
            if len(feedback_df) % 50 == 0:  # 每收集50条反馈更新一次模型
                print("检测到足够的新反馈数据，开始更新模型...")
                # 这里可以实现模型更新逻辑
                # self._retrain_xgb_model(feedback_df)
import pandas as pd
import os
import sys
sys.path.append('.')  # 确保可以导入当前目录的模块

input_csv = 'results/all_results_20250619_123847.csv'
output_csv = 'results/filtered_results_20250619_123847.csv'

def filter_has_video(input_csv, output_csv):
    # 导入关键词分类函数
    try:
        from main import load_keyword_classifications
        keyword_to_type = load_keyword_classifications()
    except ImportError:
        print("无法导入关键词分类函数，将继续但不进行分类排序")
        keyword_to_type = {}
    
    df = pd.read_csv(input_csv, encoding='utf-8')
    
    # 清理 video_url 字段
    df['video_url'] = df['video_url'].fillna('').astype(str).str.strip()
    
    # 只保留 video_url 有效的行
    filtered = df[
        (df['video_url'] != '') &
        (df['video_url'].str.lower() != 'nan') &
        (df['video_url'].str.lower() != 'none') &
        (df['video_url'].str.startswith('http'))
    ].copy()
    
    # 如果有关键词分类信息且结果不为空
    if keyword_to_type and not filtered.empty and 'keyword' in filtered.columns:
        # 添加分类信息
        filtered['keyword_type'] = filtered['keyword'].map(keyword_to_type).fillna('other')
        
        # 先按关键词分类排序（show类别优先），然后按点赞量降序排序
        filtered['is_show'] = (filtered['keyword_type'] == 'show').astype(int)
        filtered = filtered.sort_values(by=['is_show', 'attitudes_count'], ascending=[False, False])
        
        # 删除辅助排序列
        if 'is_show' in filtered.columns:
            filtered = filtered.drop(columns=['is_show'])
        if 'keyword_type' in filtered.columns:
            filtered = filtered.drop(columns=['keyword_type'])
    
    filtered.to_csv(output_csv, index=False, encoding='utf-8-sig')
    print(f'已保存只包含有视频的微博到: {output_csv}，共 {len(filtered)} 条')

if __name__ == '__main__':
    filter_has_video(input_csv, output_csv) 
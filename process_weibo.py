import pandas as pd
import re

def has_video(row):
    # Check video_url field
    if pd.notna(row['video_url']) and row['video_url'].strip() != '':
        return True
        
    # Check for t.cn video links in content
    if pd.notna(row['content']):
        # Look for http://t.cn/ links in content
        t_cn_links = re.findall(r'http://t\.cn/[A-Za-z0-9]+', row['content'])
        if t_cn_links:
            return True
            
    return False

def process_weibo_data(file_path):
    # Read CSV file
    df = pd.read_csv(file_path)
    
    # Add has_video column
    df['has_video'] = df.apply(has_video, axis=1)
    
    # Filter posts with videos
    video_posts = df[df['has_video'] == True].copy()
    
    # Add video_source column to indicate where the video was found
    def get_video_source(row):
        if pd.notna(row['video_url']) and row['video_url'].strip() != '':
            return 'video_url'
        return 't.cn_link'
    
    video_posts['video_source'] = video_posts.apply(get_video_source, axis=1)
    
    # Select relevant columns
    result = video_posts[['weibo_id', 'content', 'video_url', 'video_source']]
    
    # Save results
    output_file = file_path.replace('.csv', '_video_only.csv')
    result.to_csv(output_file, index=False)
    print(f"Found {len(result)} posts with videos")
    print(f"Results saved to: {output_file}")
    
    # Print breakdown
    print("\nBreakdown by video source:")
    print(result['video_source'].value_counts())
    
    return result

if __name__ == "__main__":
    result = process_weibo_data('results/all_results_20250621_113133.csv')
    print("\nExample posts with videos:")
    for _, row in result.iterrows():
        print(f"\nWeibo ID: {row['weibo_id']}")
        print(f"Video Source: {row['video_source']}")
        if row['video_source'] == 't.cn_link':
            t_cn_links = re.findall(r'http://t\.cn/[A-Za-z0-9]+', row['content'])
            print(f"Video Link: {t_cn_links[0]}")
        else:
            print(f"Video URL: {row['video_url']}")
        print("-" * 50) 
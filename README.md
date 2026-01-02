#geminiProject
# 1. 快速启动（交互式）
python run.py

# 2. 列出所有可用的 prompt
python run.py --list-prompts

# 3. 分析单个图片
python run.py --image 1.png --prompt color_detection_speed
python run.py --image 1.png --prompt color_detection_accuracy
python run.py --image 9.png --multi-prompt

# 4. 批量分析所有配置的图片
python run.py --all

# 5. 使用特定 prompt 批量分析
python run.py --all --prompt color_detection_speed

# 6. 使用所有 prompt 分析图片
python run.py --all --multi-prompt

# 7. 指定输出文件
python run.py --all --output my_results.json
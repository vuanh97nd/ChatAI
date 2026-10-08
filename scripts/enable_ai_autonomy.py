"""Run from the project root: python scripts/enable_ai_autonomy.py."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from assistant.config import load_config,save_config
from assistant.autonomy import grant_autonomy
save_config(grant_autonomy(load_config()))
print('Đã cấp quyền tự thực hiện công cụ ChatAI, ứng dụng đã cài, API và DeepSeek đọc PDF.')
print('Phạm vi tệp vẫn là các thư mục được cấu hình. Đóng hẳn ChatAI và mở lại để áp dụng.')

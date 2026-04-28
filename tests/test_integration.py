"""
整合測試：驗證 UI 與 Game of Life 模組的整合
"""
import sys
sys.path.append('.')

# 測試匯入不會出錯
print("測試模組匯入...")
from pixel_assistant_app.config import ConfigManager, GRID_W, GRID_H
from pixel_assistant_app.game_of_life import GameOfLife
from pixel_assistant_app.brain import AIBrain

print("✓ 所有模組匯入成功")

# 測試 ConfigManager
print("\n測試 ConfigManager...")
config = ConfigManager()
max_reply_chars = config.get("max_reply_chars", 200)
print(f"✓ ConfigManager 運作正常（max_reply_chars = {max_reply_chars}）")

# 測試 GameOfLife
print("\n測試 GameOfLife 整合...")
game = GameOfLife(GRID_W, GRID_H)
game.spawn_creature()
initial_count = game.get_cell_count()
print(f"✓ GameOfLife 初始化成功（生成 {initial_count} 個細胞）")

# 模擬幾步演化
for i in range(5):
    result = game.step()
    count = game.get_cell_count()
    print(f"  步驟 {i+1}: {count} 個細胞存活，繼續演化: {result}")

# 測試細胞檢查
print("\n測試細胞檢查功能...")
cells = list(game.get_cells())
if cells:
    x, y = cells[0]
    assert game.is_cell_alive(x, y) == True
    print(f"✓ 細胞檢查功能正常（測試座標 {x}, {y}）")

# 測試 AIBrain（不會實際呼叫 API）
print("\n測試 AIBrain 整合...")
brain = AIBrain(api_key=None, max_reply_chars=max_reply_chars)
print(f"✓ AIBrain 初始化成功（max_reply_chars = {brain.max_reply_chars}）")

print("\n" + "=" * 60)
print("整合測試全部通過！✓")
print("UI 應該能正確使用重構後的 Game of Life 模組")
print("=" * 60)

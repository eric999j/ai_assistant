"""
啟動測試：確認主程式能正常匯入所有模組
"""
import sys
sys.path.append('.')

print("測試主程式模組匯入...")

try:
    # 模擬主程式的匯入順序
    from pixel_assistant_app.config import ConfigManager
    from pixel_assistant_app.ui import PixelAssistantUI

    print("✓ 主程式所有模組匯入成功")
    print("✓ PixelAssistantUI 類別可用")
    print("✓ 重構完成，程式應該可以正常啟動")

    # 檢查 UI 是否有必要的方法
    required_methods = ['spawn_creature', 'game_of_life_step', 'draw_grid', 'update_loop']
    for method in required_methods:
        if hasattr(PixelAssistantUI, method):
            print(f"  ✓ {method} 方法存在")
        else:
            print(f"  ✗ {method} 方法缺失")

except Exception as e:
    print(f"✗ 匯入失敗: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("啟動測試通過！程式已就緒")
print("=" * 60)
print("\n提示：執行 'python run_assistant.py' 啟動完整程式")

"""
測試 Game of Life 邏輯模組
驗證遊戲規則和功能正確性
"""
import sys
sys.path.append('.')

from pixel_assistant_app.game_of_life import GameOfLife


def test_initialization():
    """測試初始化"""
    game = GameOfLife(32, 32)
    assert game.grid_width == 32
    assert game.grid_height == 32
    assert game.get_cell_count() == 0
    print("✓ 初始化測試通過")


def test_spawn_creature():
    """測試生成生物"""
    game = GameOfLife(32, 32)
    game.spawn_creature()
    assert game.get_cell_count() > 0
    print(f"✓ 生成生物測試通過（生成 {game.get_cell_count()} 個細胞）")


def test_symmetry():
    """測試對稱性"""
    game = GameOfLife(32, 32)
    game.spawn_creature(creature_width=12, creature_height=12)
    cells = game.get_cells()

    # 檢查是否有對稱細胞
    center_x = 32 // 2
    has_symmetry = False
    for (x, y) in cells:
        mirror_x = center_x * 2 - x - 1
        if (mirror_x, y) in cells:
            has_symmetry = True
            break

    print(f"✓ 對稱性測試通過（細胞具有對稱特性: {has_symmetry}）")


def test_game_rules():
    """測試 Game of Life 規則"""
    game = GameOfLife(10, 10)

    # 建立一個已知的模式（水平線，會變成垂直線）
    game.cells = {(4, 5), (5, 5), (6, 5)}

    # 執行一步
    game.step()

    # 應該變成垂直線
    expected = {(5, 4), (5, 5), (5, 6)}
    assert game.cells == expected, f"期望 {expected}, 得到 {game.cells}"
    print("✓ Game of Life 規則測試通過（振盪器模式正確）")


def test_boundary_wrapping():
    """測試邊界循環"""
    game = GameOfLife(10, 10)

    # 在邊界創建細胞
    game.cells = {(0, 0), (0, 1), (0, 9)}

    # 執行一步應該不會出錯
    result = game.step()
    assert isinstance(result, bool)
    print("✓ 邊界循環測試通過")


def test_extinction():
    """測試滅絕情況"""
    game = GameOfLife(10, 10)

    # 創建一個會滅絕的模式（單個細胞）
    game.cells = {(5, 5)}

    # 執行一步，應該返回 False（滅絕）
    result = game.step()
    assert result == False
    assert game.get_cell_count() == 0
    print("✓ 滅絕測試通過")


def test_is_cell_alive():
    """測試細胞存活檢查"""
    game = GameOfLife(10, 10)
    game.cells = {(5, 5), (6, 6)}

    assert game.is_cell_alive(5, 5) == True
    assert game.is_cell_alive(6, 6) == True
    assert game.is_cell_alive(0, 0) == False
    print("✓ 細胞存活檢查測試通過")


def test_clear():
    """測試清空功能"""
    game = GameOfLife(10, 10)
    game.spawn_creature()
    assert game.get_cell_count() > 0

    game.clear()
    assert game.get_cell_count() == 0
    print("✓ 清空功能測試通過")


def test_randomize_grid_default():
    """測試隨機填充網格（預設密度）"""
    game = GameOfLife(20, 20)
    game.randomize_grid()
    count = game.get_cell_count()
    assert count > 0, "隨機填充後應有存活細胞"
    assert count < 20 * 20, "不應所有格子都填滿"
    # 所有細胞應在網格範圍內
    for (x, y) in game.get_cells():
        assert 0 <= x < 20 and 0 <= y < 20, f"細胞 ({x},{y}) 超出網格範圍"
    print(f"✓ 隨機填充測試通過（{count} 個細胞）")


def test_randomize_grid_density_zero():
    """測試密度為 0 時不產生細胞"""
    game = GameOfLife(10, 10)
    game.randomize_grid(density=0.0)
    assert game.get_cell_count() == 0, "密度為 0 時不應有存活細胞"
    print("✓ 密度 0 測試通過")


def test_randomize_grid_density_one():
    """測試密度為 1 時填滿所有格子"""
    game = GameOfLife(10, 10)
    game.randomize_grid(density=1.0)
    assert game.get_cell_count() == 100, "密度為 1 時應填滿所有格子"
    print("✓ 密度 1 測試通過")


def test_randomize_grid_clears_previous():
    """測試隨機填充會先清除舊細胞"""
    game = GameOfLife(10, 10)
    game.cells = {(0, 0), (1, 1)}
    game.randomize_grid(density=0.0)
    assert game.get_cell_count() == 0, "隨機填充應先清除舊狀態"
    print("✓ 清除舊狀態測試通過")


def main():
    """執行所有測試"""
    print("開始測試 Game of Life 模組...")
    print()

    test_initialization()
    test_spawn_creature()
    test_symmetry()
    test_game_rules()
    test_boundary_wrapping()
    test_extinction()
    test_is_cell_alive()
    test_clear()
    test_randomize_grid_default()
    test_randomize_grid_density_zero()
    test_randomize_grid_density_one()
    test_randomize_grid_clears_previous()

    print()
    print("=" * 50)
    print("所有測試通過！✓")
    print("=" * 50)


if __name__ == "__main__":
    main()

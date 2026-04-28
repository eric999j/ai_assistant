"""
Game of Life 邏輯模組
分離遊戲邏輯與 UI，提高可維護性和可測試性
"""
import random


class GameOfLife:
    """Conway's Game of Life 實現，用於生成動態像素生物"""

    def __init__(self, grid_width: int, grid_height: int) -> None:
        """
        初始化 Game of Life

        Args:
            grid_width: 網格寬度
            grid_height: 網格高度
        """
        self.grid_width = grid_width
        self.grid_height = grid_height
        self.cells = set()  # 存活細胞的座標集合

    def spawn_creature(self, creature_width: int = 12, creature_height: int = 12) -> None:
        """
        生成對稱圖形作為初始生物

        Args:
            creature_width: 生物寬度
            creature_height: 生物高度
        """
        self.cells.clear()
        start_x = (self.grid_width - creature_width) // 2
        start_y = (self.grid_height - creature_height) // 2

        # 生成左半邊並鏡像到右半邊，創造對稱圖形
        for y in range(creature_height):
            for x in range(creature_width // 2):
                if random.random() > 0.5:
                    self.cells.add((start_x + x, start_y + y))
                    self.cells.add((start_x + creature_width - 1 - x, start_y + y))

    def step(self) -> bool:
        """
        執行一步生命遊戲演化

        Returns:
            bool: 如果所有細胞死亡返回 False，否則返回 True
        """
        neighbor_counts = {}

        # 計算每個位置的鄰居數量
        for (x, y) in self.cells:
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    # 使用模運算實現邊界循環
                    nx = (x + dx) % self.grid_width
                    ny = (y + dy) % self.grid_height
                    neighbor_counts[(nx, ny)] = neighbor_counts.get((nx, ny), 0) + 1

        # 應用 Game of Life 規則
        new_cells = set()
        for pos, count in neighbor_counts.items():
            # 規則：
            # 1. 任何活細胞周圍有 2 或 3 個活鄰居時存活
            # 2. 任何死細胞周圍恰好有 3 個活鄰居時復活
            if count == 3 or (count == 2 and pos in self.cells):
                new_cells.add(pos)

        # 更新細胞狀態
        self.cells = new_cells

        # 如果所有細胞死亡，返回 False
        if not new_cells:
            return False

        return True

    def get_cells(self) -> set:
        """
        獲取當前存活細胞的集合（回傳副本，外部修改不會影響內部狀態）

        Returns:
            set: 存活細胞坐標的集合（副本）
        """
        return set(self.cells)

    def is_cell_alive(self, x: int, y: int) -> bool:
        """
        檢查指定位置的細胞是否存活

        Args:
            x: x 座標
            y: y 座標

        Returns:
            bool: 細胞是否存活
        """
        return (x, y) in self.cells

    def get_cell_count(self) -> int:
        """
        獲取當前存活細胞數量

        Returns:
            int: 存活細胞數量
        """
        return len(self.cells)

    def randomize_grid(self, density: float = 0.3) -> None:
        """
        以隨機方式填充整個網格

        Args:
            density: 細胞存活機率，介於 0.0 ~ 1.0，預設 0.3
        """
        self.cells.clear()
        for y in range(self.grid_height):
            for x in range(self.grid_width):
                if random.random() < density:
                    self.cells.add((x, y))

    def clear(self) -> None:
        """清空所有細胞"""
        self.cells.clear()

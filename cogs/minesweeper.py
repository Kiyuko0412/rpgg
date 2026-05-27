import discord
from discord.ext import commands
from discord import app_commands
import random

class MinesweeperInputModal(discord.ui.Modal, title='踩地雷'):
    row = discord.ui.TextInput(label='橫行', placeholder='（1-9）', min_length=1, max_length=1)
    col = discord.ui.TextInput(label='直列', placeholder='（A-I）（不分大小寫）', min_length=1, max_length=1)

    def __init__(self, game, action):
        super().__init__()
        self.game = game
        self.action = action

    async def on_submit(self, interaction: discord.Interaction):
        try:
            row = int(self.row.value) - 1
            col = ord(self.col.value.upper()) - ord('A')
            if 0 <= row < self.game.height and 0 <= col < self.game.width:
                if self.action == "open":
                    result = self.game.open_cell(row, col)
                else:
                    result = self.game.flag_cell(row, col)
                await self.game.update_board(interaction)
                if result:
                    await interaction.followup.send(result, ephemeral=True)
            else:
                await interaction.response.send_message("行數在 1-9 之間，列字母在 A-I 之間（不分大小寫）。", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("請輸入對的數字和字母。", ephemeral=True)

class MinesweeperGame:
    def __init__(self, player_id, width, height, mines):
        self.player_id = player_id
        self.width = width
        self.height = height
        self.mines = mines
        self.board = self.create_board()
        self.original_board = [row[:] for row in self.board] 
        self.visible = [[False for _ in range(width)] for _ in range(height)]
        self.flags = 0
        self.game_over = False
        self.game_result = None

    def create_board(self):
        board = [[0 for _ in range(self.width)] for _ in range(self.height)]
        mine_positions = random.sample(range(self.width * self.height), self.mines)
        for pos in mine_positions:
            x, y = pos % self.width, pos // self.width
            board[y][x] = 'X'
        for y in range(self.height):
            for x in range(self.width):
                if board[y][x] == 'X':
                    continue
                board[y][x] = self.count_adjacent_mines(board, x, y)
        return board

    def count_adjacent_mines(self, board, x, y):
        count = 0
        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                if 0 <= y + dy < self.height and 0 <= x + dx < self.width:
                    if board[y + dy][x + dx] == 'X':
                        count += 1
        return count
    def open_cell(self, row, col):
        if self.visible[row][col]:
            return "已經打開了。"

        if self.board[row][col] == 'F':
            return "已經插旗了。"

        if self.original_board[row][col] == 'X':
            self.game_over = True
            self.game_result = "失敗"
            self.reveal_all()
            return "踩到地雷。"
        else:
            self.reveal(row, col)
            if self.check_win():
                self.game_over = True
                self.game_result = "勝利"
                self.reveal_all()
                return "贏了！"
        return None

    def flag_cell(self, row, col):
        if self.visible[row][col]:
            return "這個格子已經被揭開了，無法插旗。"

        if self.board[row][col] == 'F':
            self.board[row][col] = self.original_board[row][col]
            self.flags -= 1
            return "取消插旗。"
        else:
            if not hasattr(self, 'original_board'):
                self.original_board = [row[:] for row in self.board]
            self.board[row][col] = 'F'
            self.flags += 1
            return "插旗成功。"

    def reveal(self, row, col):
        if not (0 <= row < self.height and 0 <= col < self.width):
            return
        if self.visible[row][col]:
            return
        self.visible[row][col] = True
        if self.board[row][col] == 0:
            for dy in [-1, 0, 1]:
                for dx in [-1, 0, 1]:
                    self.reveal(row + dy, col + dx)

    def reveal_all(self):
        for y in range(self.height):
            for x in range(self.width):
                self.visible[y][x] = True

    def check_win(self):
        for y in range(self.height):
            for x in range(self.width):
                if self.board[y][x] != 'X' and not self.visible[y][x]:
                    return False
        return True

    def create_embed(self, player):
        embed = discord.Embed(title="踩地雷遊戲", color=0x00ff00)
        embed.set_author(name=f"{player.name}的遊戲", icon_url=player.avatar.url)
        
        # 表情符號映射
        number_emojis = ["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
        letter_emojis = ["🔠"] + [f":regional_indicator_{chr(97+i)}:" for i in range(9)]  # A到I
        
        board_str = "🟦"  # 左上角的空白格
        for i in range(self.width):
            board_str += letter_emojis[i+1]
        board_str += "\n"
        
        for y, row in enumerate(self.board):
            board_str += number_emojis[y+1]
            for x, cell in enumerate(row):
                if self.visible[y][x]:
                    original_cell = self.original_board[y][x]
                    if original_cell == 'X':
                        board_str += "💣"
                    elif original_cell == 0:
                        board_str += "⬜"
                    elif isinstance(original_cell, int) and 0 <= original_cell <= 9:
                        board_str += number_emojis[original_cell]
                    else:
                        board_str += "❓" 
                elif cell == 'F':
                    board_str += "🚩"
                else:
                    board_str += "🟦"  
            board_str += "\n"
        
        embed.add_field(name="遊戲板", value=board_str, inline=False)
        
        embed.add_field(name="剩餘地雷", value=str(self.mines - self.flags), inline=True)
        embed.add_field(name="已插旗數", value=str(self.flags), inline=True)

        if self.game_over:
            if self.game_result == "勝利":
                embed.add_field(name="遊戲狀態", value="贏了！", inline=False)
            elif self.game_result == "失敗":
                embed.add_field(name="遊戲狀態", value="踩到地雷啦", inline=False)
            else:
                embed.add_field(name="遊戲狀態", value="遊戲結束", inline=False)
        
        return embed
        
        return embed

    async def update_board(self, interaction):
        embed = self.create_embed(interaction.user)
        view = MinesweeperView(self)
        await interaction.response.edit_message(embed=embed, view=view)

class MinesweeperView(discord.ui.View):
    def __init__(self, game):
        super().__init__()
        self.game = game

    @discord.ui.button(label="開啟格子", style=discord.ButtonStyle.primary)
    async def open_cell(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.game.player_id:
            await interaction.response.send_message("這不是你的遊戲！", ephemeral=True)
            return
        await interaction.response.send_modal(MinesweeperInputModal(self.game, "open"))

    @discord.ui.button(label="插旗", style=discord.ButtonStyle.secondary)
    async def flag_cell(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.game.player_id:
            await interaction.response.send_message("這不是你的遊戲！", ephemeral=True)
            return
        await interaction.response.send_modal(MinesweeperInputModal(self.game, "flag"))

class Minesweeper(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.games = {}

    @app_commands.command(name="minesweeper", description="開始一個新的")
    @app_commands.describe(
        width="遊戲板寬度 (2-9)",
        height="遊戲板高度 (2-9)",
        mines="地雷數量"
    )
    async def minesweeper(self, interaction: discord.Interaction, width: int = 5, height: int = 5, mines: int = 5):
        if width < 2 or height < 2 or width > 9 or height > 9:
            await interaction.response.send_message("寬度和高度必須在 2 到 9 之間。", ephemeral=True)
            return
        if mines < 1 or mines >= width * height:
            await interaction.response.send_message("地雷數量必須至少為 1，且小於格子總數。", ephemeral=True)
            return

        game = MinesweeperGame(interaction.user.id, width, height, mines)
        self.games[interaction.user.id] = game

        embed = game.create_embed(interaction.user)
        view = MinesweeperView(game)

        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot: commands.Bot):
    print('>> 踩地雷系統 <<')
    await bot.add_cog(Minesweeper(bot))
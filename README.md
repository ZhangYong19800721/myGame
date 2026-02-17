# Python 坦克大战（Battle City Lite）

这是一个用 **Python + Pygame** 编写的俯视角坦克游戏，玩法类似坦克 1990：

- 你控制我方坦克，目标是保护基地。
- 敌方坦克会持续刷新并自动移动/开火。
- 你需要在基地或我方坦克被摧毁前，击毁全部敌方坦克。

## 运行方式

1. 建议先创建虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 运行游戏：

```bash
python game.py
```

## 操作说明

- 移动：`WASD` 或 方向键
- 开火：`Space`
- 重新开始：`R`（仅在胜负结算后）
- 退出：`Esc`

## 胜负条件

- **胜利**：击毁全部敌方坦克。
- **失败**：我方基地被击毁，或我方坦克被击毁。

## 游戏特点

- 可破坏砖墙与不可破坏钢墙。
- 敌方 AI 会随机巡航，且偶尔朝向玩家攻击。
- 基地周围有防御墙，可被打穿。

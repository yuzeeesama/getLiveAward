# biliscripts

自动抢 Bilibili 直播奖励（CDKey / 兑换码）的桌面工具。支持多链接并发、多线程抢奖、掉线自动重登，基于 PySide6 构建 GUI。

## 功能

- **扫码登录** — 模拟 B 站官方登录流程，Cookie 持久化存储，无需重复扫码
- **多链接批量处理** — 支持同时添加多个活动链接，独立控制每条链接的暂停 / 恢复 / 取消
- **多线程并发抢奖** — 每条链接可配置多个线程同时请求，抢到即停
- **掉线自动重登** — 抢奖过程中 Cookie 失效时会自动弹出二维码重新登录，登录后继续抢
- **日志记录** — 完整的时间戳日志输出到面板及 `data/logs/` 目录

## 截图（运行效果）

启动后粘贴 Bilibili 活动链接，点击「全部开始」即可：

```
https://www.bilibili.com/blackboard/era/award-exchange.html?task_id=xxx
```

> 链接来源：Bilibili 直播间的「礼物兑换」或「活动黑板」页面。

## 环境要求

- Python 3.10+
- Windows / macOS / Linux

## 安装

```bash
# 克隆仓库
git clone <repo-url>
cd biliscripts

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

## 运行

```bash
python app.py
```

## 使用说明

1. 打开 Bilibili 直播间，在活动面板中找到「奖励兑换」入口，复制链接地址
2. 将链接粘贴到工具输入框中（支持多条）
3. 点击 **全部开始**
4. 若未登录，会弹出二维码窗口，使用 Bilibili 手机客户端扫码确认
5. 工具自动获取奖励信息，进入抢奖状态（默认每链接 2 线程，重试 120 次）
6. 抢到 CDKey 后弹窗显示结果

## 项目结构

```
biliscripts/
├── app.py                  # 入口文件
├── requirements.txt        # 依赖清单
├── core/                   # 核心逻辑
│   ├── auth.py             # 扫码登录流程
│   ├── client.py           # Bilibili API 客户端（WBI 签名、并发请求）
│   ├── constants.py        # API 地址、配置常量、mixin key 表
│   ├── errors.py           # 自定义异常
│   ├── logging_utils.py    # 日志工具
│   ├── models.py           # 数据模型与线程控制
│   ├── service.py          # 抢奖流程编排
│   └── storage.py          # Cookie 持久化
├── ui/                     # GUI 层
│   ├── main_window.py      # 主窗口
│   ├── qr_dialog.py        # 二维码弹窗
│   └── worker.py           # 后台线程 Worker
└── data/                   # 运行时数据（gitignore）
    ├── bilibili_cookie.json
    └── logs/
```

## 免责声明

本工具仅供学习交流使用。请遵守 Bilibili 用户协议，使用者自行承担一切责任。

## License

MIT

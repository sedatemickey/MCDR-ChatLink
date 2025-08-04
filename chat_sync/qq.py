"""
QQ 机器人接口模块
基于 NoneBot2 提供 QQ 机器人功能的调用接口
"""

import asyncio
from typing import Optional, Callable, List
from mcdreforged.plugin.si.plugin_server_interface import PluginServerInterface

from .config import ChatSyncConfig
from .nonebot import nonebot_manager
from .utils import mcdr_logger


class QQBot:
    """QQ 机器人接口类"""

    def __init__(self):
        self.logger = mcdr_logger
        self.is_enabled = False
        self.server: Optional[PluginServerInterface] = None

    def initialize(self, server: PluginServerInterface, host: str = "127.0.0.1",
                  port: int = 8080, access_token: Optional[str] = None,
                  log_level: str = "WARNING"):
        """初始化 QQ 机器人"""
        try:
            if not nonebot_manager.check_availability():
                self.logger.error("NoneBot2 未安装，请运行: pip install nonebot2 nonebot-adapter-onebot")
                return False

            self.server = server

            # 初始化 NoneBot2
            nonebot_manager.initialize(
                host=host,
                port=port,
                access_token=access_token,
                server=server,
                log_level=log_level
            )

            # 注册默认的消息处理器
            # self._register_default_handlers()

            self.is_enabled = True
            self.logger.debug("QQ 机器人初始化成功")
            return True

        except Exception as e:
            self.logger.error(f"QQ 机器人初始化失败: {e}")
            return False

    def start(self):
        """启动 QQ 机器人"""
        if not self.is_enabled:
            self.logger.error("QQ 机器人未初始化")
            return False

        try:
            nonebot_manager.start()
            self.logger.info("QQ 机器人已启动")
            return True
        except Exception as e:
            self.logger.error(f"启动 QQ 机器人失败: {e}")
            return False

    def stop(self):
        """停止 QQ 机器人"""
        try:
            nonebot_manager.stop()
            self.is_enabled = False
            self.logger.info("QQ 机器人已停止")
        except Exception as e:
            self.logger.error(f"停止 QQ 机器人失败: {e}")

    # def _register_default_handlers(self):
    #     """注册默认的消息处理器"""
    #     # 注册群消息处理器
    #     nonebot_manager.register_message_callback('group', self._handle_group_message)

    #     # 注册私聊消息处理器
    #     nonebot_manager.register_message_callback('private', self._handle_private_message)

    # async def _handle_group_message(self, bot, group_id: int, user_id: int,
    #                               nickname: str, message: str, event):
    #     """默认群消息处理器"""
    #     self.logger.info(f"群消息 - 群:{group_id}, 用户:{nickname}({user_id}), 消息:{message}")

    #     # 这里可以添加默认的消息处理逻辑
    #     # 例如：转发到 Minecraft 服务器
    #     if self.server:
    #         self.server.logger.info(f"[QQ群{group_id}] {nickname}: {message}")

    # async def _handle_private_message(self, bot, user_id: int, nickname: str,
    #                                 message: str, event):
    #     """默认私聊消息处理器"""
    #     self.logger.info(f"私聊消息 - 用户:{nickname}({user_id}), 消息:{message}")

    #     # 这里可以添加默认的私聊处理逻辑
    #     if self.server:
    #         self.server.logger.info(f"[QQ私聊] {nickname}: {message}")

    def register_group_message_handler(self, handler: Callable):
        """注册群消息处理器"""
        nonebot_manager.register_message_callback('group', handler)

    def register_private_message_handler(self, handler: Callable):
        """注册私聊消息处理器"""
        nonebot_manager.register_message_callback('private', handler)

    async def send_group_message(self, group_id: int, message: str) -> bool:
        """发送群消息"""
        return await nonebot_manager.send_group_message(group_id, message)

    async def send_private_message(self, user_id: int, message: str) -> bool:
        """发送私聊消息"""
        return await nonebot_manager.send_private_message(user_id, message)

    def is_connected(self) -> bool:
        """检查机器人是否已连接"""
        return nonebot_manager.is_bot_connected()

    def get_bot_info(self):
        """获取机器人信息"""
        return nonebot_manager.get_bot_info()


# 全局 QQ 机器人实例
qq_bot = QQBot()


# ==================== 便捷函数 ====================

def init_qq_bot(server: PluginServerInterface, config: ChatSyncConfig) -> bool:
    """初始化 QQ 机器人"""
    host = config.onebot_ws_host
    port = config.onebot_ws_port
    access_token = config.onebot_access_token
    return qq_bot.initialize(server, host, port, access_token)


def start_qq_bot() -> bool:
    """启动 QQ 机器人"""
    return qq_bot.start()


def stop_qq_bot():
    """停止 QQ 机器人"""
    qq_bot.stop()


async def send_to_qq_group(group_id: int, message: str) -> bool:
    """发送消息到 QQ 群"""
    return await qq_bot.send_group_message(group_id, message)


async def send_to_qq_user(user_id: int, message: str) -> bool:
    """发送私聊消息"""
    return await qq_bot.send_private_message(user_id, message)


def register_qq_group_handler(handler: Callable):
    """注册群消息处理器"""
    qq_bot.register_group_message_handler(handler)


def register_qq_private_handler(handler: Callable):
    """注册私聊消息处理器"""
    qq_bot.register_private_message_handler(handler)


def is_qq_bot_connected() -> bool:
    """检查 QQ 机器人连接状态"""
    return qq_bot.is_connected()


# ==================== 示例函数 ====================

async def example_group_message_handler(bot, group_id: int, user_id: int,
                                      nickname: str, message: str, event):
    """示例：群消息处理器"""
    # 检查是否是命令
    if message.startswith("/"):
        command = message[1:].strip().split()

        if len(command) == 0:
            return

        cmd = command[0].lower()

        if cmd == "ping":
            await bot.send_group_msg(group_id=group_id, message="pong!")

        elif cmd == "time":
            import datetime
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            await bot.send_group_msg(group_id=group_id, message=f"当前时间: {now}")

        elif cmd == "bind" and len(command) >= 2:
            game_nickname = command[1]
            # 这里可以调用用户绑定逻辑
            await bot.send_group_msg(
                group_id=group_id,
                message=f"用户 {nickname} 已绑定游戏昵称: {game_nickname}"
            )

        elif cmd == "help":
            help_text = """可用命令:
!ping - 测试机器人响应
!time - 获取当前时间
!bind <游戏昵称> - 绑定游戏昵称
!help - 显示帮助信息"""
            await bot.send_group_msg(group_id=group_id, message=help_text)

    else:
        # 普通消息，可以转发到 Minecraft
        print(f"[转发到MC] 群{group_id} {nickname}: {message}")


async def example_private_message_handler(bot, user_id: int, nickname: str,
                                        message: str, event):
    """示例：私聊消息处理器"""
    if message.lower() == "hello":
        await bot.send_private_msg(
            user_id=user_id,
            message=f"你好 {nickname}！我是 ChatSync 机器人。"
        )
    elif message.lower() == "help":
        help_text = """ChatSync 机器人帮助:
- 发送 'hello' 获取问候
- 发送 'status' 查看服务器状态
- 在群聊中使用 !help 查看更多命令"""
        await bot.send_private_msg(user_id=user_id, message=help_text)


def setup_example_handlers():
    """设置示例处理器"""
    register_qq_group_handler(example_group_message_handler)
    register_qq_private_handler(example_private_message_handler)


async def example_send_mc_message_to_qq(player_name: str, message: str, target_groups: List[int]):
    """示例：将 MC 消息发送到 QQ 群"""
    if not is_qq_bot_connected():
        print("QQ 机器人未连接，无法发送消息")
        return

    formatted_message = f"[MC] <{player_name}> {message}"

    for group_id in target_groups:
        success = await send_to_qq_group(group_id, formatted_message)
        if success:
            print(f"消息已发送到群 {group_id}")
        else:
            print(f"发送到群 {group_id} 失败")


async def example_send_server_status(target_groups: List[int], status: str):
    """示例：发送服务器状态到 QQ 群"""
    if not is_qq_bot_connected():
        print("QQ 机器人未连接，无法发送消息")
        return

    status_message = f"[服务器状态] {status}"

    for group_id in target_groups:
        await send_to_qq_group(group_id, status_message)


async def example_send_player_join_leave(player_name: str, action: str, target_groups: List[int]):
    """示例：发送玩家加入/离开消息到 QQ 群"""
    if not is_qq_bot_connected():
        return

    if action == "join":
        message = f"[MC] 玩家 {player_name} 加入了服务器"
    elif action == "leave":
        message = f"[MC] 玩家 {player_name} 离开了服务器"
    else:
        message = f"[MC] 玩家 {player_name} {action}"

    for group_id in target_groups:
        await send_to_qq_group(group_id, message)


# ==================== 使用示例 ====================

def example_usage():
    """使用示例"""
    print("""
QQ 机器人使用示例:

1. 初始化和启动:
   from chat_sync.qq import init_qq_bot, start_qq_bot, setup_example_handlers

   # 在 MCDR 插件的 on_load 中
   if init_qq_bot(server, host="127.0.0.1", port=8080):
       setup_example_handlers()  # 设置示例处理器
       start_qq_bot()

2. 发送消息到 QQ:
   import asyncio
   from chat_sync.qq import send_to_qq_group

   # 发送消息到群
   asyncio.create_task(send_to_qq_group(123456789, "Hello from Minecraft!"))

3. 处理 MC 消息:
   from chat_sync.qq import example_send_mc_message_to_qq

   # 在处理 MC 玩家消息时
   target_groups = [123456789, 987654321]
   asyncio.create_task(example_send_mc_message_to_qq("Steve", "Hello QQ!", target_groups))

4. 自定义消息处理器:
   from chat_sync.qq import register_qq_group_handler

   async def my_group_handler(bot, group_id, user_id, nickname, message, event):
       if message == "!server":
           await bot.send_group_msg(group_id=group_id, message="服务器运行正常!")

   register_qq_group_handler(my_group_handler)

5. 机器人框架配置 (LLOneBot 示例):
   在 LLOneBot 配置中设置反向 WebSocket:
   {
     "reverseWs": {
       "enable": true,
       "urls": ["ws://127.0.0.1:8080/onebot/v11/ws"]
     }
   }
""")
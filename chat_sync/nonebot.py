"""
NoneBot2 集成模块
提供 QQ 机器人功能的核心实现
"""

import asyncio
import threading
from typing import Optional, Callable, Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from nonebot.adapters.onebot.v11 import Bot
from mcdreforged.plugin.si.plugin_server_interface import PluginServerInterface

from .utils import mcdr_logger

try:
    import nonebot
    from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter
    from nonebot.adapters.onebot.v11 import Bot, MessageEvent, GroupMessageEvent, PrivateMessageEvent
    from nonebot import on_message, on_notice, on_request
    from nonebot.rule import to_me
    NONEBOT_AVAILABLE = True
except ImportError:
    NONEBOT_AVAILABLE = False
    # 定义占位符以避免未绑定错误
    nonebot = None
    OneBotV11Adapter = None
    Bot = None
    MessageEvent = None
    GroupMessageEvent = None
    PrivateMessageEvent = None
    on_message = None
    on_notice = None
    on_request = None
    to_me = None


class NoneBotManager:
    """NoneBot2 管理器"""

    def __init__(self):
        self.is_initialized = False
        self.is_running = False
        self.bot_instance: Optional[Any] = None
        self.server: Optional[PluginServerInterface] = None
        self.logger = mcdr_logger

        # 回调函数
        self.message_callbacks: Dict[str, List[Callable]] = {
            'group': [],
            'private': []
        }
        self.event_callbacks: Dict[str, List[Callable]] = {}

        # 运行时状态
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None

        # 处理器注册状态
        self._handlers_registered = False

    def check_availability(self) -> bool:
        """检查 NoneBot2 是否可用"""
        return NONEBOT_AVAILABLE

    def initialize(self, host: str = "127.0.0.1", port: int = 8080,
                  access_token: Optional[str] = None,
                  server: Optional[PluginServerInterface] = None,
                  log_level: str = "WARNING"):
        """初始化 NoneBot2 WebSocket 服务器"""
        if not self.check_availability():
            raise ImportError("NoneBot2 未安装，请运行: pip install nonebot2 nonebot-adapter-onebot")

        # 如果已经初始化，先停止之前的实例
        if self.is_initialized or self.is_running:
            self.logger.warning("NoneBot2 已经初始化，正在重新初始化...")
            self.stop()
            # 重置初始化状态
            self.is_initialized = False

        self.server = server

        try:
            # 初始化 NoneBot
            config = {
                "host": host,
                "port": port,
                "log_level": log_level,
                "driver": "~fastapi+~httpx+~websockets",
                "onebot_access_token": access_token or "",
                # 添加服务器配置，允许端口重用
                "fastapi_reload": False,
                "fastapi_debug": False,
            }

            # 确保 nonebot 模块可用
            if nonebot is None:
                raise RuntimeError("NoneBot2 模块不可用")

            # 检查是否已经有 NoneBot 实例，如果有则清理
            try:
                existing_driver = nonebot.get_driver()
                if existing_driver:
                    self.logger.warning("检测到已存在的 NoneBot 实例，正在清理...")
                    # 重置 NoneBot 的全局状态
                    nonebot._driver = None
            except Exception as e:
                # 没有现有实例或清理失败，继续初始化
                self.logger.debug(f"清理现有 NoneBot 实例时出错: {e}")

            nonebot.init(**config)

            # 注册适配器
            driver = nonebot.get_driver()
            if OneBotV11Adapter is not None:
                # 注册适配器，NoneBot2 会自动创建 WebSocket 服务器端点
                driver.register_adapter(OneBotV11Adapter)

            # 注册事件处理器
            self._register_handlers()

            # 注册机器人连接事件
            self._register_bot_events()

            self.is_initialized = True
            self.logger.info(f"NoneBot2 初始化成功 - ws://{host}:{port}/onebot/v11/ws")

        except Exception as e:
            self.logger.error(f"NoneBot2 初始化失败: {e}")
            raise

    def _register_handlers(self):
        """注册消息处理器"""
        if not NONEBOT_AVAILABLE or on_message is None:
            return

        # 避免重复注册处理器
        if self._handlers_registered:
            self.logger.debug("消息处理器已注册，跳过重复注册")
            return

        # 群消息处理器
        from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent

        group_handler = on_message()

        @group_handler.handle()
        async def handle_group_message(bot: Bot, event: GroupMessageEvent):
            try:
                group_id = event.group_id
                user_id = event.user_id
                message = str(event.message).strip()
                sender = event.sender
                nickname = sender.nickname if sender else f"用户{user_id}"

                self.logger.debug(f"nonebot收到群消息 - 群:{group_id}, 用户:{nickname}({user_id}), 消息:{message}")

                # 调用注册的回调函数
                for callback in self.message_callbacks.get('group', []):
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(bot, group_id, user_id, nickname, message, event)
                        else:
                            callback(bot, group_id, user_id, nickname, message, event)
                    except Exception as e:
                        self.logger.error(f"群消息回调函数执行失败: {e}")

            except Exception as e:
                self.logger.error(f"处理群消息时出错: {e}")

        # 私聊消息处理器
        private_handler = on_message()

        @private_handler.handle()
        async def handle_private_message(bot: Bot, event: PrivateMessageEvent):
            try:
                user_id = event.user_id
                message = str(event.message).strip()
                sender = event.sender
                nickname = sender.nickname if sender else f"用户{user_id}"

                self.logger.debug(f"nonebot收到私聊消息 - 用户:{nickname}({user_id}), 消息:{message}")

                # 调用注册的回调函数
                for callback in self.message_callbacks.get('private', []):
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(bot, user_id, nickname, message, event)
                        else:
                            callback(bot, user_id, nickname, message, event)
                    except Exception as e:
                        self.logger.error(f"私聊消息回调函数执行失败: {e}")

            except Exception as e:
                self.logger.error(f"处理私聊消息时出错: {e}")

        # 标记处理器已注册
        self._handlers_registered = True
        self.logger.debug("消息处理器注册完成")

    def _register_bot_events(self):
        """注册机器人连接事件"""
        if not NONEBOT_AVAILABLE or nonebot is None:
            return

        driver = nonebot.get_driver()

        @driver.on_bot_connect
        async def on_bot_connect(bot):
            self.bot_instance = bot
            self.logger.info(f"机器人 {bot.self_id} 连接成功")

        @driver.on_bot_disconnect
        async def on_bot_disconnect(bot):
            if self.bot_instance == bot:
                self.bot_instance = None
            self.logger.info(f"机器人 {bot.self_id} 断开连接")

    def register_message_callback(self, message_type: str, callback: Callable):
        """注册消息回调函数"""
        if message_type not in self.message_callbacks:
            self.message_callbacks[message_type] = []
        self.message_callbacks[message_type].append(callback)
        self.logger.debug(f"已注册 {message_type} 消息回调函数")

    def register_event_callback(self, event_type: str, callback: Callable):
        """注册事件回调函数"""
        if event_type not in self.event_callbacks:
            self.event_callbacks[event_type] = []
        self.event_callbacks[event_type].append(callback)
        self.logger.debug(f"已注册 {event_type} 事件回调函数")

    def start(self):
        """启动 NoneBot2 WebSocket 服务器"""
        if not self.is_initialized:
            raise RuntimeError("NoneBot2 未初始化，请先调用 initialize()")

        if self.is_running:
            self.logger.warning("NoneBot2 WebSocket 服务器已在运行")
            return

        def run_bot():
            """在新线程中运行 WebSocket 服务器"""
            try:
                # 创建新的事件循环
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                self._loop = loop

                # 运行 NoneBot WebSocket 服务器
                if nonebot is not None:
                    self.logger.debug("正在启动 NoneBot2 WebSocket 服务器...")

                    # 添加重试机制处理端口占用
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            nonebot.run()
                            break
                        except Exception as e:
                            if "10048" in str(e) and attempt < max_retries - 1:
                                self.logger.warning(f"端口被占用，等待2秒后重试... (尝试 {attempt + 1}/{max_retries})")
                                import time
                                time.sleep(2)
                            else:
                                raise e

            except Exception as e:
                if "10048" in str(e):
                    self.logger.error(f"NoneBot2 WebSocket 服务器启动失败: 端口被占用，请检查是否有其他实例在运行")
                else:
                    self.logger.error(f"NoneBot2 WebSocket 服务器运行出错: {e}")
            finally:
                self.is_running = False
        
        self._thread = threading.Thread(target=run_bot, daemon=True, name="NoneBot2-WebSocket-Thread")
        self._thread.start()
        self.is_running = True
        self.logger.debug("NoneBot2 WebSocket 服务器已在后台线程启动")

    def stop(self):
        """停止 NoneBot2 WebSocket 服务器"""
        if not self.is_running:
            return

        try:
            self.logger.debug("正在停止 NoneBot2 WebSocket 服务器...")

            # 标记为停止状态
            self.is_running = False

            # 清理机器人实例
            self.bot_instance = None

            # 强制关闭 NoneBot2 驱动器和服务器
            try:
                if NONEBOT_AVAILABLE and nonebot is not None:
                    # 重置 NoneBot 的全局驱动器
                    nonebot._driver = None
                    self.logger.debug("已重置 NoneBot 驱动器")
            except Exception as e:
                self.logger.debug(f"关闭驱动器时出错: {e}")

            # 停止事件循环
            if self._loop and not self._loop.is_closed():
                try:
                    # 在事件循环中执行关闭操作
                    future = asyncio.run_coroutine_threadsafe(self._shutdown(), self._loop)
                    future.result(timeout=3.0)  # 减少等待时间到3秒
                except Exception as e:
                    self.logger.debug(f"异步关闭失败: {e}")

                try:
                    # 停止事件循环
                    self._loop.call_soon_threadsafe(self._loop.stop)
                except Exception as e:
                    self.logger.debug(f"停止事件循环失败: {e}")

            # 等待线程结束
            if self._thread and self._thread.is_alive():
                try:
                    self._thread.join(timeout=3.0)  # 减少等待时间到3秒
                    if self._thread.is_alive():
                        self.logger.debug("NoneBot2 线程未能在3秒内正常结束，强制继续")
                except Exception as e:
                    self.logger.debug(f"等待线程结束失败: {e}")

            # 清理资源
            self._loop = None
            self._thread = None

            # 清理回调函数
            self.message_callbacks.clear()
            self.event_callbacks.clear()

            # 重置初始化状态
            self.is_initialized = False

            # 重置处理器注册状态
            self._handlers_registered = False

            # 等待端口释放
            import time
            time.sleep(1)  # 等待1秒让端口完全释放

            self.logger.info("NoneBot2 WebSocket 服务器已停止")

        except Exception as e:
            self.logger.error(f"停止 NoneBot2 时出错: {e}")
            # 强制重置所有状态
            self.is_running = False
            self.is_initialized = False
            self.bot_instance = None
            self._loop = None
            self._thread = None

    async def _shutdown(self):
        """异步关闭"""
        try:
            # 清理 NoneBot 相关资源
            if NONEBOT_AVAILABLE and nonebot is not None:
                try:
                    # 重置 NoneBot 的全局驱动器
                    nonebot._driver = None
                    self.logger.debug("已清理 NoneBot 驱动器")
                except Exception as e:
                    self.logger.error(f"清理 NoneBot 驱动器时出错: {e}")

            # 清理其他资源
            self.bot_instance = None

        except Exception as e:
            self.logger.error(f"异步关闭时出错: {e}")

    async def send_group_message(self, group_id: int, message: str) -> bool:
        """发送群消息"""
        if not self.bot_instance:
            self.logger.warning("机器人未连接，无法发送消息")
            return False
        
        try:
            await self.bot_instance.send_group_msg(group_id=group_id, message=message)
            self.logger.debug(f"已发送群消息到 {group_id}: {message}")
            return True
        except Exception as e:
            self.logger.error(f"发送群消息失败: {e}")
            return False

    async def send_private_message(self, user_id: int, message: str) -> bool:
        """发送私聊消息"""
        if not self.bot_instance:
            self.logger.warning("机器人未连接，无法发送消息")
            return False
        
        try:
            await self.bot_instance.send_private_msg(user_id=user_id, message=message)
            self.logger.debug(f"已发送私聊消息到 {user_id}: {message}")
            return True
        except Exception as e:
            self.logger.error(f"发送私聊消息失败: {e}")
            return False

    def is_bot_connected(self) -> bool:
        """检查机器人是否已连接"""
        return self.bot_instance is not None

    def get_bot_info(self) -> Optional[Dict[str, Any]]:
        """获取机器人信息"""
        if not self.bot_instance:
            return None
        
        return {
            "self_id": self.bot_instance.self_id,
            "adapter": self.bot_instance.adapter.get_name(),
            "is_connected": True
        }


# 全局实例
nonebot_manager = NoneBotManager()

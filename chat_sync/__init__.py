import asyncio
from mcdreforged.plugin.si.plugin_server_interface import PluginServerInterface
from mcdreforged.info_reactor.info import Info
from typing import Optional

from .config import load_chat_sync_config, load_user_bind_config
from .config import ChatSyncConfig, UserBindConfig
from .utils import should_filter_message
from .network import network_manager
from .utils import mcdr_logger
from .utils import get_player_list, get_all_player_lists
from .qq import (
    init_qq_bot, start_qq_bot, stop_qq_bot,
    send_to_qq_group, send_to_qq_user,
    register_qq_group_handler, register_qq_private_handler,
    is_qq_bot_connected, setup_example_handlers,
    example_send_mc_message_to_qq, example_send_player_join_leave
)

config: ChatSyncConfig
user_bind_config: UserBindConfig
plugin_server: PluginServerInterface

class ChatSyncObj:
    """ChatSync 消息对象"""
    def __init__(self, type: int, server_name: str, player: str | None, message: str):
        self.type = type  # 0: 取得玩家消息 1:取得玩家事件信息 2: 发送玩家消息 3: 发送玩家事件信息 4: 发送QQ群消息 5: 玩家列表请求 6: 玩家列表回复
        self.server_name = server_name
        self.player = player
        self.message = message

    def to_dict(self):
        """序列化为字典"""
        return {
            'type': self.type,
            'server_name': self.server_name,
            'player': self.player,
            'message': self.message
        }

    @classmethod
    def from_dict(cls, data: dict):
        """从字典反序列化"""
        return cls(
            type=data['type'],
            server_name=data['server_name'],
            player=data.get('player'),
            message=data['message']
        )
    

def on_load(server: PluginServerInterface, prev_module):
    """
    插件加载完成时，加载配置文件，注册监听器
    """
    global config, user_bind_config, plugin_server
    plugin_server = server
    # 获取插件配置
    config = load_chat_sync_config(server)
    user_bind_config = load_user_bind_config(server)
    # 注册事件监听器
    server.register_event_listener("PlayerDeathEvent", on_player_death)
    server.register_event_listener("PlayerAdvancementEvent", on_player_advancement)
    # 初始化logger
    mcdr_logger.init(server)
    # 网络管理器
    network_manager.initialize(server, config)
    network_manager.register_message_handler(handle_network_message)
    network_manager.start()
    # qq机器人
    if config.qq_bot_enabled and config.main_server:
        success = init_qq_bot(
            server=server,
            config=config
        )
        if success:
            # 注册自定义消息处理器
            register_qq_group_handler(on_qq_group_message)
            
            # 或者使用示例处理器
            # setup_example_handlers()
            
            # 启动机器人
            start_qq_bot()
        else:
            server.logger.error("nonebot服务初始化失败")
        
    mcdr_logger.info("ChatSync loaded")


async def on_qq_group_message(bot, group_id, user_id, nickname, message, event):
    """
    处理QQ群消息
    """
    global plugin_server
    server = plugin_server
    if message.startswith("/"):
        # 处理指令
        command_parts = message[1:].strip().split()
        if len(command_parts) == 0:
            return

        command = command_parts[0].lower()

        if command == "bind":
            if len(command_parts) < 2:
                await send_to_qq_group(group_id, f"用法: /bind <游戏昵称>")
                return

            username = command_parts[1]

            # 验证用户名格式（可选，根据需要调整）
            if len(username) < 3 or len(username) > 16:
                await send_to_qq_group(group_id, f"游戏昵称长度必须在3-16个字符之间")
                return

            # 检查是否已经绑定
            if user_bind_config.is_bound(user_id):
                old_username = user_bind_config.get_bound_nickname(user_id)
                await send_to_qq_group(group_id, f"您已绑定昵称 {old_username}，如需更换请先使用 /unbind 解绑")
                return

            # 检查用户名是否已被其他人绑定
            for existing_qq_id, existing_username in user_bind_config.qqid_nickname.items():
                if existing_username == username and existing_qq_id != str(user_id):
                    await send_to_qq_group(group_id, f"昵称 {username} 已被其他用户绑定")
                    return

            # 执行绑定
            try:
                user_bind_config.bind(user_id, username)
                await send_to_qq_group(group_id, f"绑定成功！用户 {nickname} 已绑定游戏昵称: {username}")
                mcdr_logger.info(f"用户 {nickname}({user_id}) 绑定游戏昵称: {username}")
            except Exception as e:
                await send_to_qq_group(group_id, f"绑定失败: {str(e)}")
                mcdr_logger.error(f"绑定失败: {e}")

        elif command == "unbind":
            if not user_bind_config.is_bound(user_id):
                await send_to_qq_group(group_id, f"您尚未绑定任何昵称")
                return

            try:
                old_username = user_bind_config.get_bound_nickname(user_id)
                user_bind_config.unbind(user_id)
                await send_to_qq_group(group_id, f"解绑成功！已解除与昵称 {old_username} 的绑定")
                mcdr_logger.info(f"用户 {nickname}({user_id}) 解绑游戏昵称: {old_username}")
            except Exception as e:
                await send_to_qq_group(group_id, f"解绑失败: {str(e)}")
                mcdr_logger.error(f"解绑失败: {e}")

        elif command == "help":
            help_text = """可用指令:
/bind <游戏昵称> - 绑定游戏昵称
/unbind - 解绑当前昵称
/list - 查看在线玩家列表
/help - 显示帮助信息"""
            await send_to_qq_group(group_id, help_text)
        
        elif command == "list":
            player_list = await get_all_player_lists(plugin_server, config)
            mcdr_logger.debug(f"取得玩家列表: {player_list}")
            mcdr_logger.info(f"发送玩家列表到群 {group_id}")
            await send_to_qq_group(group_id, player_list)

        else:
            await send_to_qq_group(group_id, f"未知指令: /{command}，使用 /help 查看可用指令")

        return
    
    if not config.sync_qq_to_mc:
        return
    mcdr_logger.debug(f"开始处理 {group_id} 群消息: {user_id} -> {message}")

    if group_id in config.qq_group_id:
        if should_filter_message(config, message):
            mcdr_logger.debug(f"消息被过滤，跳过")
            return

        # 检查user_id是否已经绑定了nickname
        if user_bind_config.is_bound(user_id):
            bound_nickname = user_bind_config.get_bound_nickname(user_id)
            mcdr_logger.debug(f"用户 {user_id} 已绑定昵称: {bound_nickname}")
            chat_sync_obj = ChatSyncObj(4, config.mc_server_name, bound_nickname, message)
            if config.sync_qq_to_mc:
                # 构造 ChatSyncObj 并发送到MC服务器
                forward_to_game(chat_sync_obj, False)
                network_manager.send_chat_sync_message(chat_sync_obj)
            if config.sync_qq_to_qq:
                forward_to_qq_group(chat_sync_obj, False, exclude_group=group_id)
        else:
            mcdr_logger.debug(f"用户 {user_id} 未绑定昵称")
            await send_to_qq_group(group_id, f"用户 {nickname} 未绑定昵称，使用 /bind <游戏昵称> 来绑定你的游戏昵称")
            

        # TODO: 在这里添加消息转发到MC的逻辑
        # 可以使用 display_name 作为显示的玩家名称

    else:
        mcdr_logger.debug(f"群 {group_id} 不在同步列表中，跳过")
        


def handle_network_message(message_data, sender_id):
    """处理来自网络的 ChatSyncObj 消息"""
    global plugin_server
    try:
        # 处理接收到的 ChatSyncObj 消息
        chat_sync_data = message_data.get("data")

        # 将字典数据反序列化为 ChatSyncObj 对象
        if isinstance(chat_sync_data, dict):
            chat_sync_obj = ChatSyncObj.from_dict(chat_sync_data)
        else:
            chat_sync_obj = chat_sync_data  # 兼容性处理

        if chat_sync_obj.type == 0:  # 副服务器发来的玩家消息
            # 只有主服务器才处理这种类型的消息
            if not config.main_server:
                mcdr_logger.error(f"副服务器收到了 type=0 消息，这不应该发生")

            # 广播到其他副服务器
            if config.sync_mc_to_mc:
                forward_to_game(chat_sync_obj, False)
                # 创建新的对象避免修改原对象
                broadcast_chat_sync_obj = ChatSyncObj(2, chat_sync_obj.server_name, chat_sync_obj.player, chat_sync_obj.message)
                network_manager.send_chat_sync_message(broadcast_chat_sync_obj, exclude_client=sender_id)

            # 广播到QQ群
            if config.sync_mc_to_qq:
                forward_to_qq_group(chat_sync_obj, False)            

        elif chat_sync_obj.type == 1:  # 副服务器发来的玩家事件消息
            # 只有主服务器才处理这种类型的消息
            if not config.main_server:
                mcdr_logger.error(f"副服务器收到了 type=1 消息，这不应该发生")

            # 广播到其他副服务器
            if config.sync_mc_to_mc:
                forward_to_game(chat_sync_obj, True)
                # 创建新的对象避免修改原对象
                broadcast_chat_sync_obj = ChatSyncObj(3, chat_sync_obj.server_name, chat_sync_obj.player, chat_sync_obj.message)
                network_manager.send_chat_sync_message(broadcast_chat_sync_obj, exclude_client=sender_id)

            # 广播到QQ群
            if config.sync_mc_to_qq:
                forward_to_qq_group(chat_sync_obj, True)

        elif chat_sync_obj.type == 2:  # 主服务器发来的玩家消息（发送给副服务器）
            # 只有副服务器才应该收到这种消息
            if config.main_server:
                mcdr_logger.error(f"主服务器收到了 type=2 消息，这不应该发生")
            forward_to_game(chat_sync_obj, False)

        elif chat_sync_obj.type == 3:  # 主服务器发来的玩家事件信息（发送给副服务器）
            # 只有副服务器才应该收到这种消息
            if config.main_server:
                mcdr_logger.error(f"主服务器收到了 type=3 消息，这不应该发生")
            forward_to_game(chat_sync_obj, True)

        elif chat_sync_obj.type == 4:  # QQ群消息
            # 所有服务器都显示QQ消息
            forward_to_game(chat_sync_obj, False)

        elif chat_sync_obj.type == 5:  # 玩家列表请求
            # 只有副服务器才应该收到这种消息
            if config.main_server:
                mcdr_logger.error(f"主服务器收到了 type=5 消息，这不应该发生")
            else:
                # 副服务器处理玩家列表请求
                request_id = chat_sync_obj.message
                player_list = get_player_list(plugin_server, config)
                # 发送回复，消息格式为 "request_id|player_list_content"
                reply_message = f"{request_id}|{player_list}"
                reply_obj = ChatSyncObj(6, config.mc_server_name, None, reply_message)
                network_manager.send_chat_sync_message(reply_obj)
                mcdr_logger.debug(f"已回复玩家列表请求: {request_id}")

        elif chat_sync_obj.type == 6:  # 玩家列表回复
            # 只有主服务器才应该收到这种消息
            if not config.main_server:
                mcdr_logger.error(f"副服务器收到了 type=6 消息，这不应该发生")
            # 主服务器的回复处理由 get_all_player_lists 函数中的临时处理器处理
            mcdr_logger.debug(f"收到玩家列表回复: {chat_sync_obj.message[:50]}...")

        else:
            raise ValueError(f"未知的 ChatSyncObj 类型: {chat_sync_obj.type}")

        mcdr_logger.debug(f"收到网络消息: {chat_sync_obj}")

    except Exception as e:
        mcdr_logger.error(f"处理网络消息失败: {e}")
        

def forward_to_game(chat_sync_obj: ChatSyncObj, is_event: bool):
    if chat_sync_obj.type == 4:
        formatted_message = config.qq_chat_format.format(
            player=chat_sync_obj.player or "未知玩家",
            message=chat_sync_obj.message
        )
        plugin_server.say(formatted_message)
        mcdr_logger.info(f"已同步来自 QQ 的消息: {formatted_message}")
        return
    if not is_event:
        formatted_message = config.mc_chat_format.format(
            server=chat_sync_obj.server_name,
            player=chat_sync_obj.player or "未知玩家",
            message=chat_sync_obj.message
        )
        plugin_server.say(formatted_message)
        mcdr_logger.info(f"已同步来自 {chat_sync_obj.server_name} 的消息: {formatted_message}")
    else:
        formatted_message = config.mc_event_format.format(
            server=chat_sync_obj.server_name,
            message=chat_sync_obj.message
        )
        plugin_server.say(formatted_message)
        mcdr_logger.info(f"已同步来自 {chat_sync_obj.server_name} 的事件: {formatted_message}")
    
    
def _safe_send_to_qq_group(group_id: int, message: str):
    """发送消息到QQ群，处理异步调用"""
    # 输入验证
    if not isinstance(group_id, int) or group_id <= 0:
        mcdr_logger.error(f"无效的群ID: {group_id}")
        return

    if not isinstance(message, str) or not message.strip():
        mcdr_logger.error("消息内容不能为空")
        return

    # 消息长度限制
    if len(message) > 1000:
        message = message[:997] + "..."
        mcdr_logger.warning("消息过长，已截断")

    try:
        # 尝试获取当前运行的事件循环
        asyncio.get_running_loop()
        # 如果有运行的事件循环，创建任务
        asyncio.create_task(send_to_qq_group(group_id, message))
    except RuntimeError:
        # 如果没有运行的事件循环，在新线程中运行
        import threading
        def run_async():
            try:
                asyncio.run(send_to_qq_group(group_id, message))
            except Exception as e:
                mcdr_logger.error(f"发送QQ消息失败: {e}")
        thread = threading.Thread(target=run_async, name=f"QQ-Send-{group_id}")
        thread.daemon = True
        thread.start()

def forward_to_qq_group(chat_sync_obj: ChatSyncObj, is_event: bool, exclude_group: Optional[int] = None):
    """转发消息到QQ群"""
    if not config.qq_group_id:
        return

    # 根据消息类型选择格式
    if not is_event:
        formatted_message = config.mc_chat_format.format(
            server=chat_sync_obj.server_name,
            player=chat_sync_obj.player or "未知玩家",
            message=chat_sync_obj.message
        )
        log_type = "消息"
    else:
        formatted_message = config.mc_event_format.format(
            server=chat_sync_obj.server_name,
            message=chat_sync_obj.message
        )
        log_type = "事件"

    # 发送到所有配置的QQ群
    for group_id in config.qq_group_id:
        if exclude_group and group_id == exclude_group:
            continue
        _safe_send_to_qq_group(group_id, formatted_message)

    mcdr_logger.info(f"已同步来自 {chat_sync_obj.server_name} 的{log_type}到QQ群: {formatted_message}")


def on_info(server: PluginServerInterface, info: Info):
    """
    处理玩家发送的信息
    """
    if info.is_player and info.player is not None and info.content is not None:
        player_name = info.player
        message_content = info.content
        mcdr_logger.debug(f"玩家 {player_name} 发送消息: {message_content}")
        
        # 检查消息过滤设置
        if should_filter_message(config, message_content):
            return

        # 广播消息
        if config.main_server:
            # 主服务器：直接发送给副服务器，并同步到QQ
            chat_sync_obj = ChatSyncObj(2, config.mc_server_name, player_name, message_content)
            network_manager.send_chat_sync_message(chat_sync_obj)
            if config.sync_mc_to_qq:
                forward_to_qq_group(chat_sync_obj, False)
        else:
            # 副服务器：发送给主服务器处理
            chat_sync_obj = ChatSyncObj(0, config.mc_server_name, player_name, message_content)
            network_manager.send_chat_sync_message(chat_sync_obj)
            # 副服务器不直接同步到QQ，由主服务器处理
        

def on_player_joined(server: PluginServerInterface, player_name: str, info: Info):
    """
    处理玩家加入事件
    """
    mcdr_logger.debug(f"玩家加入: {player_name}")
    
    if not config.sync_player_join_leave:
        return
    
    # 广播消息
    if config.main_server:
        # 主服务器：直接发送给副服务器，并同步到QQ
        chat_sync_obj = ChatSyncObj(3, config.mc_server_name, player_name, f"{player_name}加入了游戏")
        network_manager.send_chat_sync_message(chat_sync_obj)
        if config.sync_mc_to_qq:
            forward_to_qq_group(chat_sync_obj, True)
    else:
        # 副服务器：发送给主服务器处理
        chat_sync_obj = ChatSyncObj(1, config.mc_server_name, player_name, f"{player_name}加入了游戏")
        network_manager.send_chat_sync_message(chat_sync_obj)
        # 副服务器不直接同步到QQ，由主服务器处理


def on_player_left(server: PluginServerInterface, player_name: str):
    """
    处理玩家离开事件
    """
    mcdr_logger.debug(f"玩家离开: {player_name}")
    
    if not config.sync_player_join_leave:
        return
    
    # 广播消息
    if config.main_server:
        # 主服务器：直接发送给副服务器，并同步到QQ
        chat_sync_obj = ChatSyncObj(3, config.mc_server_name, player_name, f"{player_name}离开了游戏")
        network_manager.send_chat_sync_message(chat_sync_obj)
        if config.sync_mc_to_qq:
            forward_to_qq_group(chat_sync_obj, True)
    else:
        # 副服务器：发送给主服务器处理
        chat_sync_obj = ChatSyncObj(1, config.mc_server_name, player_name, f"{player_name}离开了游戏")
        network_manager.send_chat_sync_message(chat_sync_obj)
        # 副服务器不直接同步到QQ，由主服务器处理


def on_player_death(server: PluginServerInterface, player: str, event: str, content):
    """
    处理玩家死亡事件
    """
    zh_content = ""
    for i in content:
        if i.locale == 'zh_cn':
            zh_content = i.raw
            break
    mcdr_logger.debug(f"玩家 {player} 死亡: {zh_content}")
    
    if not config.sync_player_death:
        return
    
    # 广播消息
    if config.main_server:
        # 主服务器：直接发送给副服务器，并同步到QQ
        chat_sync_obj = ChatSyncObj(3, config.mc_server_name, player, zh_content)
        network_manager.send_chat_sync_message(chat_sync_obj)
        if config.sync_mc_to_qq:
            forward_to_qq_group(chat_sync_obj, True)
    else:
        # 副服务器：发送给主服务器处理
        chat_sync_obj = ChatSyncObj(1, config.mc_server_name, player, zh_content)
        network_manager.send_chat_sync_message(chat_sync_obj)
        # 副服务器不直接同步到QQ，由主服务器处理


def on_player_advancement(server: PluginServerInterface, player: str, event: str, content):
    """
    处理玩家成就事件
    """
    zh_content = ""
    for i in content:
        if i.locale == 'zh_cn':
            zh_content = i.raw
            break
    mcdr_logger.debug(f"玩家 {player} 成就: {zh_content}")
    
    if not config.sync_player_advancement:
        return
    
    # 广播消息
    if config.main_server:
        # 主服务器：直接发送给副服务器，并同步到QQ
        chat_sync_obj = ChatSyncObj(3, config.mc_server_name, player, zh_content)
        network_manager.send_chat_sync_message(chat_sync_obj)
        if config.sync_mc_to_qq:
            forward_to_qq_group(chat_sync_obj, True)
    else:
        # 副服务器：发送给主服务器处理
        chat_sync_obj = ChatSyncObj(1, config.mc_server_name, player, zh_content)
        network_manager.send_chat_sync_message(chat_sync_obj)
        # 副服务器不直接同步到QQ，由主服务器处理



def on_unload(server: PluginServerInterface):
    """插件卸载时的清理工作"""
    try:
        # 停止网络服务
        network_manager.stop()
        mcdr_logger.info("网络服务已停止")

        # 停止 QQ 机器人服务
        stop_qq_bot()

    except Exception as e:
        mcdr_logger.error(f"插件卸载时出错: {e}")

    mcdr_logger.info("ChatSync 插件已卸载")


if __name__ == "__main__":
    print("Hello World!")
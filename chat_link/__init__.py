from mcdreforged.plugin.si.plugin_server_interface import PluginServerInterface
from mcdreforged.info_reactor.info import Info

from .config import load_chat_link_config, load_user_bind_config
from .config import ChatLinkConfig, UserBindConfig
from .utils import should_filter_message
from .network import network_manager
from .utils import mcdr_logger

config: ChatLinkConfig
user_bind_config: UserBindConfig
plugin_server: PluginServerInterface

class ChatLinkObj:
    """ChatLink 消息对象"""
    def __init__(self, type: int, server_name: str, player: str | None, message: str):
        self.type = type  # 0: 取得玩家消息 1:取得玩家事件信息 2: 发送玩家消息 3: 发送玩家事件信息 4: 发送QQ群消息
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
    config = load_chat_link_config(server)
    user_bind_config = load_user_bind_config(server)
    # 注册事件监听器
    server.register_event_listener("PlayerDeathEvent", on_player_death)
    server.register_event_listener("PlayerAdvancementEvent", on_player_advancement)
    # 初始化logger
    mcdr_logger.init(server)
    # 网络管理器
    network_manager.initialize(server, config)
    network_manager.register_message_handler(handle_network_message)
    if network_manager.start():
        mcdr_logger.info("网络服务启动成功")
    else:
        mcdr_logger.error("网络服务启动失败")
        
    server.logger.info("ChatLink loaded")


def handle_network_message(message_data, sender_id):
    """处理来自网络的 ChatLinkObj 消息"""
    global plugin_server
    try:
        # 处理接收到的 ChatLinkObj 消息
        chat_link_data = message_data.get("data")
        
        # 将字典数据反序列化为 ChatLinkObj 对象
        if isinstance(chat_link_data, dict):
            chat_link_obj = ChatLinkObj.from_dict(chat_link_data)
        else:
            chat_link_obj = chat_link_data  # 兼容性处理
            
        if chat_link_obj.type == 0:  # 取得玩家消息
            # 广播到子服务器
            boardcast_chat_link_obj = chat_link_obj
            boardcast_chat_link_obj.type = 2
            network_manager.send_chat_link_message(boardcast_chat_link_obj, exclude_client=sender_id)

            # 使用配置的格式发送消息到 MC 服务器
            forward_to_game(chat_link_obj, False)
            
        elif chat_link_obj.type == 1:  # 取得玩家事件消息
            # 广播到子服务器
            boardcast_chat_link_obj = chat_link_obj
            boardcast_chat_link_obj.type = 3
            network_manager.send_chat_link_message(boardcast_chat_link_obj, exclude_client=sender_id)

            # 使用配置的格式发送消息到 MC 服务器
            forward_to_game(chat_link_obj, True)
            
        elif chat_link_obj.type == 2:  # 发送玩家消息
            forward_to_game(chat_link_obj, False)
        
        elif chat_link_obj.type == 3:  # 发送玩家事件信息
            forward_to_game(chat_link_obj, True)
        
        elif chat_link_obj.type == 4:  # 发送QQ群消息
            pass
        
        else:
            raise ValueError(f"未知的 ChatLinkObj 类型: {chat_link_obj.type}")
        
        mcdr_logger.debug(f"收到网络消息: {chat_link_obj}")
        
    except Exception as e:
        mcdr_logger.error(f"处理网络消息失败: {e}")
        

def forward_to_game(chat_link_obj: ChatLinkObj, is_event: bool):
    if not is_event:
        formatted_message = config.mc_chat_format.format(
            server=chat_link_obj.server_name,
            player=chat_link_obj.player or "未知玩家",
            message=chat_link_obj.message
        )
        plugin_server.say(formatted_message)
        mcdr_logger.info(f"已同步来自 {chat_link_obj.server_name} 的消息: {formatted_message}")
    else:
        formatted_message = config.mc_event_format.format(
            server=chat_link_obj.server_name,
            message=chat_link_obj.message
        )
        plugin_server.say(formatted_message)
        mcdr_logger.info(f"已同步来自 {chat_link_obj.server_name} 的事件: {formatted_message}")
    


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
        chat_link_obj = ChatLinkObj(2 if config.main_server else 0, config.mc_server_name, player_name, message_content)
        network_manager.send_chat_link_message(chat_link_obj)
        

def on_player_joined(server: PluginServerInterface, player_name: str, info: Info):
    """
    处理玩家加入事件
    """
    mcdr_logger.debug(f"玩家加入: {player_name}")
    
    if not config.sync_player_join_leave:
        return
    
    # 广播消息
    chat_link_obj = ChatLinkObj(3 if config.main_server else 1, config.mc_server_name, player_name, f"{player_name}加入了游戏")
    network_manager.send_chat_link_message(chat_link_obj)


def on_player_left(server: PluginServerInterface, player_name: str):
    """
    处理玩家离开事件
    """
    mcdr_logger.debug(f"玩家离开: {player_name}")
    
    if not config.sync_player_join_leave:
        return
    
    # 广播消息
    chat_link_obj = ChatLinkObj(3 if config.main_server else 1, config.mc_server_name, player_name, f"{player_name}离开了游戏")
    network_manager.send_chat_link_message(chat_link_obj)


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
    chat_link_obj = ChatLinkObj(3 if config.main_server else 1, config.mc_server_name, player, zh_content)
    network_manager.send_chat_link_message(chat_link_obj)


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
    chat_link_obj = ChatLinkObj(3 if config.main_server else 1, config.mc_server_name, player, zh_content)
    network_manager.send_chat_link_message(chat_link_obj)


def on_qq_message(qqid: str, message: str):
    """
    处理QQ群消息
    """
    global plugin_server
    server = plugin_server
    mcdr_logger.debug(f"QQ群消息: {qqid} -> {message}")


def on_unload(server: PluginServerInterface):
    """插件卸载时的清理工作"""
    network_manager.stop()
    mcdr_logger.info("网络服务已停止")


if __name__ == "__main__":
    print("Hello World!")
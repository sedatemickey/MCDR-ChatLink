from typing import Dict, cast, Optional
from mcdreforged.utils.serializer import Serializable
from mcdreforged.plugin.si.plugin_server_interface import PluginServerInterface


class ChatLinkConfig(Serializable):
    """ChatLink 插件配置类"""
    
    # ChatLink 主副服务器配置
    main_server: bool = True
    main_server_host: str = "127.0.0.1"
    main_server_port: int = 29530
    main_server_password: str = ""

    # QQ 机器人配置
    qq_bot_enabled: bool = False
    onebot_api_host: str = "127.0.0.1"
    onebot_api_port: int = 8080
    qq_group_id: list[int] = []

    # Minecraft 服务器配置
    mc_server_name: str = "我的服务器"
    mc_chat_format: str = "[{server}] <{player}> {message}"
    mc_event_format: str = "[{server}] {message}"
    qq_chat_format: str = "[{server}] <{player}> {message}"
    qq_event_format: str = "[{server}] {message}"

    # 消息同步设置
    sync_mc_to_qq: bool = True
    sync_qq_to_mc: bool = True
    sync_mc_to_mc: bool = True
    sync_qq_to_qq: bool = True
    # sync_server_start_stop: bool = True
    sync_player_join_leave: bool = True
    sync_player_death: bool = True
    sync_player_advancement: bool = True

    # 消息过滤设置
    filter_commands: bool = True
    filter_prefixes: list = ["/", "!", ".", "#"]
    max_message_length: int = 200
    
    
class UserBindConfig(Serializable):
    """QQ号与游戏昵称绑定 配置类"""
    qqid_nickname: Dict[str, str] = {}  # 键为QQ号，值为游戏昵称

    def __init__(self):
        super().__init__()
        self._server: Optional[PluginServerInterface] = None

    def set_server(self, server: PluginServerInterface):
        """设置服务器接口，用于保存配置"""
        self._server = server

    def bind(self, qqid: str, nickname: str) -> 'UserBindConfig':
        """
        绑定QQ号与游戏昵称

        :param qqid: QQ号
        :param nickname: 游戏昵称
        :return: 返回自身以支持链式调用
        """
        if self._server is None:
            raise RuntimeError("Server interface not set. Call set_server() first.")

        self.qqid_nickname[qqid] = nickname
        self._server.save_config_simple(self, "userbind.json")
        return self


def load_chat_link_config(server: PluginServerInterface) -> ChatLinkConfig:
    return cast(ChatLinkConfig, server.load_config_simple(target_class=ChatLinkConfig))

def load_user_bind_config(server: PluginServerInterface) -> UserBindConfig:
    config = cast(UserBindConfig, server.load_config_simple("userbind.json",target_class=UserBindConfig))
    config.set_server(server)
    return config


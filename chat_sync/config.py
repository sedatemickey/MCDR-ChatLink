from typing import Dict, cast, Optional
from mcdreforged.utils.serializer import Serializable
from mcdreforged.plugin.si.plugin_server_interface import PluginServerInterface


class ChatSyncConfig(Serializable):
    """ChatSync 插件配置类"""

    # ChatSync 主副服务器配置
    main_server: bool = True
    main_server_host: str = "127.0.0.1"
    main_server_port: int = 29530
    main_server_password: str = ""

    def validate(self) -> bool:
        """验证配置的有效性"""
        # 验证端口范围
        if not (1024 <= self.main_server_port <= 65535):
            raise ValueError(f"端口号必须在1024-65535范围内，当前值: {self.main_server_port}")

        # 验证QQ群ID
        for group_id in self.qq_group_id:
            if not isinstance(group_id, int) or group_id <= 0:
                raise ValueError(f"无效的QQ群ID: {group_id}")

        # 验证消息长度限制
        if self.max_message_length <= 0:
            raise ValueError(f"消息长度限制必须大于0，当前值: {self.max_message_length}")

        return True

    # QQ 机器人配置
    qq_bot_enabled: bool = False
    onebot_ws_host: str = "127.0.0.1"
    onebot_ws_port: int = 8080
    onebot_access_token: str = ""
    qq_group_id: list[int] = []

    # 保留原有配置作为向后兼容
    # onebot_api_host: str = "127.0.0.1"
    # onebot_api_port: int = 8080

    # Minecraft 服务器配置
    mc_server_name: str = "我的服务器"
    mc_chat_format: str = "[{server}] <{player}> {message}"
    mc_event_format: str = "[{server}] {message}"
    qq_chat_format: str = "[QQ] <{player}> {message}"

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

    def bind(self, qqid: int, nickname: str) -> 'UserBindConfig':
        """
        绑定QQ号与游戏昵称

        :param qqid: QQ号
        :param nickname: 游戏昵称
        :return: 返回自身以支持链式调用
        """
        if self._server is None:
            raise RuntimeError("Server interface not set. Call set_server() first.")

        self.qqid_nickname[str(qqid)] = nickname
        self._server.save_config_simple(self, "userbind.json")
        return self

    def get_bound_nickname(self, qqid: int) -> Optional[str]:
        """
        获取QQ号绑定的游戏昵称

        :param qqid: QQ号
        :return: 绑定的游戏昵称，如果未绑定则返回None
        """
        return self.qqid_nickname.get(str(qqid))

    def is_bound(self, qqid: int) -> bool:
        """
        检查QQ号是否已绑定游戏昵称

        :param qqid: QQ号
        :return: 如果已绑定返回True，否则返回False
        """
        return str(qqid) in self.qqid_nickname

    def unbind(self, qqid: int) -> bool:
        """
        解除QQ号与游戏昵称的绑定

        :param qqid: QQ号
        :return: 如果成功解绑返回True，如果QQ号未绑定返回False
        """
        if self._server is None:
            raise RuntimeError("Server interface not set. Call set_server() first.")

        if str(qqid) in self.qqid_nickname:
            del self.qqid_nickname[str(qqid)]
            self._server.save_config_simple(self, "userbind.json")
            return True
        return False


def load_chat_sync_config(server: PluginServerInterface) -> ChatSyncConfig:
    config = cast(ChatSyncConfig, server.load_config_simple(target_class=ChatSyncConfig))
    try:
        config.validate()
    except ValueError as e:
        server.logger.error(f"配置验证失败: {e}")
        raise
    return config

def load_user_bind_config(server: PluginServerInterface) -> UserBindConfig:
    config = cast(UserBindConfig, server.load_config_simple("userbind.json",target_class=UserBindConfig))
    config.set_server(server)
    return config


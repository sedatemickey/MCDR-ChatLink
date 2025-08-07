import asyncio
import time
from typing import Dict, Optional
from mcdreforged.plugin.si.plugin_server_interface import PluginServerInterface

from .config import ChatSyncConfig

def should_filter_message(config: ChatSyncConfig, message: str) -> bool:
    """
    检查消息是否应该被过滤
    """

    # 如果启用了命令过滤
    if config.filter_commands:
        # 检查消息是否以过滤前缀开头
        for prefix in config.filter_prefixes:
            if message.startswith(prefix):
                return True

    # 检查消息长度
    if len(message) > config.max_message_length:
        return True

    return False

def get_player_list(server: PluginServerInterface, config: ChatSyncConfig) -> str:
    """获取在线玩家列表"""
    online_player_api = server.get_plugin_instance("online_player_api")
    if online_player_api is None:
        mcdr_logger.error("online_player_api 插件未找到或未加载，无法获取在线玩家列表")
        return f"---{config.mc_server_name}---\n获取失败"

    try:
        online_players = f"---{config.mc_server_name}---"
        for player in online_player_api.get_player_list():
            online_players += f"\n{player}"
        return online_players
    except Exception as e:
        mcdr_logger.error(f"获取在线玩家列表时发生错误: {e}")
        return f"---{config.mc_server_name}---\n获取失败"
    
async def get_all_player_lists(server: PluginServerInterface, config: ChatSyncConfig) -> str:
    """获取所有服务器的在线玩家列表"""
    from .network import network_manager
    from . import ChatSyncObj

    if not config.main_server:
        mcdr_logger.error("只有主服务器可以调用 get_all_player_lists 函数")
        return f"---{config.mc_server_name}---\n错误：只有主服务器可以获取所有服务器玩家列表"

    # 获取主服务器自己的玩家列表
    main_server_list = get_player_list(server, config)

    # 如果没有副服务器连接，直接返回主服务器列表
    if not network_manager.client_connections:
        return main_server_list

    # 生成唯一的请求ID
    request_id = f"player_list_request_{int(time.time() * 1000)}"

    # 存储回复的字典
    responses: Dict[str, str] = {}

    # 创建玩家列表请求消息
    request_obj = ChatSyncObj(5, config.mc_server_name, None, request_id)  # type=5: 玩家列表请求

    # 注册临时消息处理器来接收回复
    def handle_player_list_response(data: Dict, sender_id: str):
        try:
            chat_sync_obj = ChatSyncObj.from_dict(data.get("data", {}))
            if chat_sync_obj.type == 6 and chat_sync_obj.message.startswith(request_id + "|"):  # type=6: 玩家列表回复
                # 提取实际的玩家列表内容（去掉请求ID前缀和分隔符）
                player_list_content = chat_sync_obj.message[len(request_id) + 1:]  # +1 for the "|" separator
                responses[sender_id] = player_list_content
                mcdr_logger.debug(f"收到来自 {sender_id} 的玩家列表回复")
        except Exception as e:
            mcdr_logger.error(f"处理玩家列表回复时出错: {e}")

    # 注册临时处理器
    network_manager.register_message_handler(handle_player_list_response)

    try:
        # 发送请求到所有副服务器
        network_manager.send_chat_sync_message(request_obj)
        mcdr_logger.debug(f"已发送玩家列表请求: {request_id}")

        # 等待回复，最多等待10秒
        expected_responses = len(network_manager.client_connections)
        start_time = time.time()
        timeout = 10.0

        while len(responses) < expected_responses and (time.time() - start_time) < timeout:
            await asyncio.sleep(0.1)

        # 移除临时处理器
        if handle_player_list_response in network_manager.message_handlers:
            network_manager.message_handlers.remove(handle_player_list_response)

        # 组合所有服务器的玩家列表
        all_lists = [main_server_list]
        all_lists.extend(responses.values())

        # 如果有服务器没有回复，添加超时信息
        if len(responses) < expected_responses:
            missing_count = expected_responses - len(responses)
            timeout_info = f"---超时服务器---\n{missing_count}个服务器未在10秒内回复"
            all_lists.append(timeout_info)

        return "\n\n".join(all_lists)

    except Exception as e:
        # 确保移除临时处理器
        if handle_player_list_response in network_manager.message_handlers:
            network_manager.message_handlers.remove(handle_player_list_response)
        mcdr_logger.error(f"获取所有服务器玩家列表时出错: {e}")
        return f"{main_server_list}\n\n---错误---\n获取其他服务器列表失败: {str(e)}"


class Logger:
    def init(self, server: PluginServerInterface):
        self.server = server

    def debug(self, message: str):
        self.server.logger.debug(message)

    def info(self, message: str):
        self.server.logger.info(message)

    def warning(self, message: str):
        self.server.logger.warning(message)

    def error(self, message: str):
        self.server.logger.error(message)
        
mcdr_logger = Logger()
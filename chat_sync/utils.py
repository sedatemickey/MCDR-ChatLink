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
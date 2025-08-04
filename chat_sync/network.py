"""
ChatSync 网络通信模块
实现主副服务器之间的socket通信功能
"""

import socket
import threading
import json
import time
from typing import Optional, Callable, Dict, List, Any
from mcdreforged.plugin.si.plugin_server_interface import PluginServerInterface

from .config import ChatSyncConfig
from .utils import mcdr_logger


class NetworkManager:
    """网络通信管理器"""

    def __init__(self):
        self.logger = mcdr_logger
        self.server: Optional[PluginServerInterface] = None
        self.config: Optional[ChatSyncConfig] = None

        # 服务器模式相关
        self.is_main_server = True
        self.socket_server: Optional[socket.socket] = None
        self.client_connections: Dict[str, socket.socket] = {}  # 客户端连接字典
        self.server_thread: Optional[threading.Thread] = None

        # 客户端模式相关
        self.client_socket: Optional[socket.socket] = None
        self.client_thread: Optional[threading.Thread] = None
        self.is_connected = False

        # 消息处理回调
        self.message_handlers: List[Callable[[Any, str], None]] = []

        # 运行状态
        self.is_running = False
        self.should_stop = False

    def initialize(self, server: PluginServerInterface, config: ChatSyncConfig):
        """初始化网络管理器"""
        self.server = server
        self.config = config
        self.is_main_server = config.main_server

        self.logger.info(f"网络管理器初始化 - 模式: {'主服务器' if self.is_main_server else '副服务器'}")

    def start(self) -> bool:
        """启动网络服务"""
        if self.is_running:
            self.logger.warning("网络服务已在运行")
            return True

        if not self.config:
            self.logger.error("配置未初始化")
            return False

        try:
            if self.is_main_server:
                return self._start_server()
            else:
                return self._start_client()
        except Exception as e:
            self.logger.error(f"启动网络服务失败: {e}")
            return False

    def stop(self):
        """停止网络服务"""
        if not self.is_running:
            return

        self.should_stop = True
        self.is_running = False

        try:
            if self.is_main_server:
                self._stop_server()
            else:
                self._stop_client()
        except Exception as e:
            self.logger.error(f"停止网络服务时出错: {e}")

    def _start_server(self) -> bool:
        """启动主服务器"""
        if not self.config:
            self.logger.error("配置未初始化，无法启动服务器")
            return False

        try:
            self.socket_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket_server.bind((self.config.main_server_host, self.config.main_server_port))
            self.socket_server.listen(10)

            self.server_thread = threading.Thread(target=self._server_loop, daemon=True)
            self.server_thread.start()

            self.is_running = True
            self.logger.info(f"主服务器启动成功 - {self.config.main_server_host}:{self.config.main_server_port}")
            return True

        except Exception as e:
            self.logger.error(f"启动主服务器失败: {e}")
            return False

    def _start_client(self) -> bool:
        """启动副服务器客户端"""
        try:
            self.client_thread = threading.Thread(target=self._client_loop, daemon=True)
            self.client_thread.start()

            self.is_running = True
            self.logger.info("副服务器客户端启动成功")
            return True

        except Exception as e:
            self.logger.error(f"启动副服务器客户端失败: {e}")
            return False

    def _stop_server(self):
        """停止主服务器"""
        if self.socket_server:
            try:
                self.socket_server.close()
            except:
                pass
            self.socket_server = None

        # 关闭所有客户端连接
        for client_id, client_socket in self.client_connections.items():
            try:
                client_socket.close()
            except:
                pass
        self.client_connections.clear()

        self.logger.info("主服务器已停止")

    def _stop_client(self):
        """停止副服务器客户端"""
        self.is_connected = False

        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None

        self.logger.info("副服务器客户端已停止")

    def _server_loop(self):
        """主服务器循环"""
        while not self.should_stop and self.socket_server:
            try:
                client_socket, client_address = self.socket_server.accept()
                self.logger.debug(f"新客户端连接: {client_address}")

                # 在新线程中处理客户端
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, client_address),
                    daemon=True
                )
                client_thread.start()

            except Exception as e:
                if not self.should_stop:
                    self.logger.error(f"服务器循环出错: {e}")
                break

    def _handle_client(self, client_socket: socket.socket, client_address):
        """处理客户端连接"""
        client_id = f"{client_address[0]}:{client_address[1]}"

        try:
            # 密码验证
            if not self._authenticate_client(client_socket):
                self.logger.warning(f"客户端 {client_id} 认证失败")
                client_socket.close()
                return

            self.client_connections[client_id] = client_socket
            self.logger.info(f"客户端 {client_id} 认证成功")

            # 处理客户端消息
            while not self.should_stop:
                try:
                    data = self._receive_message(client_socket)
                    if data is None:
                        break

                    self.logger.debug(f"收到来自 {client_id} 的消息: {data}")

                    # 处理消息
                    self._handle_received_message(data, client_id)

                except Exception as e:
                    self.logger.error(f"处理客户端 {client_id} 消息时出错: {e}")
                    break

        except Exception as e:
            self.logger.error(f"处理客户端 {client_id} 时出错: {e}")
        finally:
            # 清理连接
            if client_id in self.client_connections:
                del self.client_connections[client_id]
            try:
                client_socket.close()
            except:
                pass
            self.logger.info(f"客户端 {client_id} 已断开连接")

    def _client_loop(self):
        """副服务器客户端循环"""
        while not self.should_stop:
            try:
                if not self.is_connected:
                    self._connect_to_server()

                if self.is_connected and self.client_socket:
                    try:
                        data = self._receive_message(self.client_socket)
                        if data is None:
                            self.is_connected = False
                            continue

                        self.logger.debug(f"收到来自主服务器的消息: {data}")

                        # 处理消息
                        self._handle_received_message(data, "main_server")

                    except Exception as e:
                        self.logger.error(f"处理主服务器消息时出错: {e}")
                        self.is_connected = False

                else:
                    time.sleep(5)  # 重连间隔

            except Exception as e:
                self.logger.error(f"客户端循环出错: {e}")
                time.sleep(5)

    def _connect_to_server(self) -> bool:
        """连接到主服务器"""
        if not self.config:
            self.logger.error("配置未初始化，无法连接到服务器")
            return False

        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.config.main_server_host, self.config.main_server_port))

            # 密码认证
            if not self._authenticate_to_server():
                self.logger.error("向主服务器认证失败")
                self.client_socket.close()
                self.client_socket = None
                return False

            self.is_connected = True
            self.logger.info(f"已连接到主服务器 {self.config.main_server_host}:{self.config.main_server_port}")
            return True

        except Exception as e:
            self.logger.error(f"连接主服务器失败: {e}")
            if self.client_socket:
                try:
                    self.client_socket.close()
                except:
                    pass
                self.client_socket = None
            return False

    def _authenticate_client(self, client_socket: socket.socket) -> bool:
        """验证客户端密码"""
        if not self.config:
            self.logger.error("配置未初始化，无法进行客户端认证")
            return False

        try:
            # 接收认证消息
            auth_data = self._receive_message(client_socket)
            if not auth_data or auth_data.get("type") != "auth":
                return False

            password = auth_data.get("password", "")
            if password == self.config.main_server_password:
                # 发送认证成功响应
                self._send_message(client_socket, {"type": "auth_response", "success": True})
                return True
            else:
                # 发送认证失败响应
                self._send_message(client_socket, {"type": "auth_response", "success": False})
                return False

        except Exception as e:
            self.logger.error(f"客户端认证过程出错: {e}")
            return False

    def _authenticate_to_server(self) -> bool:
        """向主服务器进行认证"""
        if not self.config:
            self.logger.error("配置未初始化，无法进行服务器认证")
            return False

        if not self.client_socket:
            self.logger.error("客户端socket未初始化，无法进行认证")
            return False

        try:
            # 发送认证消息
            auth_message = {"type": "auth", "password": self.config.main_server_password}
            self._send_message(self.client_socket, auth_message)

            # 接收认证响应
            response = self._receive_message(self.client_socket)
            if response and response.get("type") == "auth_response":
                return response.get("success", False)

            return False

        except Exception as e:
            self.logger.error(f"向主服务器认证时出错: {e}")
            return False

    def _send_message(self, sock: socket.socket, data: Dict[str, Any]):
        """发送消息"""
        try:
            message = json.dumps(data, ensure_ascii=False)
            message_bytes = message.encode('utf-8')
            message_length = len(message_bytes)

            # 发送消息长度（4字节）
            sock.sendall(message_length.to_bytes(4, byteorder='big'))
            # 发送消息内容
            sock.sendall(message_bytes)

        except Exception as e:
            self.logger.error(f"发送消息失败: {e}")
            raise

    def _receive_message(self, sock: socket.socket) -> Optional[Dict[str, Any]]:
        """接收消息"""
        try:
            # 接收消息长度（4字节）
            length_bytes = self._receive_exact(sock, 4)
            if not length_bytes:
                return None

            message_length = int.from_bytes(length_bytes, byteorder='big')

            # 接收消息内容
            message_bytes = self._receive_exact(sock, message_length)
            if not message_bytes:
                return None

            message = message_bytes.decode('utf-8')
            return json.loads(message)

        except Exception as e:
            self.logger.error(f"接收消息失败: {e}")
            return None

    def _receive_exact(self, sock: socket.socket, length: int) -> Optional[bytes]:
        """精确接收指定长度的数据"""
        data = b''
        while len(data) < length:
            try:
                chunk = sock.recv(length - len(data))
                if not chunk:
                    return None
                data += chunk
            except Exception:
                return None
        return data

    def _handle_received_message(self, data: Dict[str, Any], sender_id: str):
        """处理接收到的消息"""
        try:
            message_type = data.get("type")

            if message_type == "chat_sync_obj":
                # 处理 ChatSyncObj 消息
                self._handle_chat_sync_message(data, sender_id)
            elif message_type == "ping":
                # 处理心跳消息
                self._handle_ping_message(data, sender_id)
            else:
                self.logger.warning(f"未知消息类型: {message_type}")

        except Exception as e:
            self.logger.error(f"处理消息时出错: {e}")

    def _handle_chat_sync_message(self, data: Dict[str, Any], sender_id: str):
        """处理 ChatSyncObj 消息"""
        try:
            # 调用注册的消息处理器
            for handler in self.message_handlers:
                try:
                    handler(data, sender_id)
                except Exception as e:
                    self.logger.error(f"消息处理器执行失败: {e}")

            # 如果是主服务器，需要转发给其他副服务器
            if self.is_main_server and sender_id != "main_server":
                self._broadcast_to_clients(data, exclude_client=sender_id)

        except Exception as e:
            self.logger.error(f"处理 ChatSyncObj 消息时出错: {e}")

    def _handle_ping_message(self, data: Dict[str, Any], sender_id: str):
        """处理心跳消息"""
        # 回复 pong
        pong_message = {"type": "pong", "timestamp": time.time()}

        if self.is_main_server:
            # 主服务器回复给客户端
            client_socket = self.client_connections.get(sender_id)
            if client_socket:
                self._send_message(client_socket, pong_message)
        else:
            # 副服务器回复给主服务器
            if self.client_socket:
                self._send_message(self.client_socket, pong_message)

    def _broadcast_to_clients(self, data: Dict[str, Any], exclude_client: Optional[str] = None):
        """广播消息给所有客户端（除了指定排除的客户端）"""
        if not self.is_main_server:
            return

        for client_id, client_socket in self.client_connections.items():
            if exclude_client and client_id == exclude_client:
                continue

            try:
                self._send_message(client_socket, data)
            except Exception as e:
                self.logger.error(f"向客户端 {client_id} 广播消息失败: {e}")

    # ==================== 公共接口方法 ====================

    def register_message_handler(self, handler: Callable[[Any, str], None]):
        """注册消息处理器"""
        self.message_handlers.append(handler)
        self.logger.info("已注册消息处理器")

    def send_chat_sync_message(self, chat_sync_obj: Any, exclude_client: Optional[str] = None) -> bool:
        """发送 ChatSyncObj 消息"""
        try:
            # 将 ChatSyncObj 序列化为字典
            if hasattr(chat_sync_obj, 'to_dict'):
                chat_sync_data = chat_sync_obj.to_dict()
            else:
                # 兼容性处理，如果不是 ChatSyncObj 对象
                chat_sync_data = chat_sync_obj.__dict__

            message = {
                "type": "chat_sync_obj",
                "data": chat_sync_data,
                "timestamp": time.time()
            }

            if self.is_main_server:
                # 主服务器广播给所有副服务器
                self._broadcast_to_clients(message, exclude_client=exclude_client)
                self.logger.debug(f"已广播网络消息: {chat_sync_obj}")
                return True
            else:
                # 副服务器发送给主服务器
                if self.is_connected and self.client_socket:
                    self._send_message(self.client_socket, message)
                    mcdr_logger.debug(f"已向主服务器发送网络消息: {chat_sync_obj}")
                    return True
                else:
                    self.logger.warning("未连接到主服务器，无法发送消息")
                    return False

        except Exception as e:
            self.logger.error(f"发送 ChatSyncObj 消息失败: {e}")
            return False

    def send_ping(self) -> bool:
        """发送心跳消息"""
        try:
            ping_message = {"type": "ping", "timestamp": time.time()}

            if self.is_main_server:
                # 主服务器向所有客户端发送心跳
                self._broadcast_to_clients(ping_message)
                return True
            else:
                # 副服务器向主服务器发送心跳
                if self.is_connected and self.client_socket:
                    self._send_message(self.client_socket, ping_message)
                    return True
                else:
                    return False

        except Exception as e:
            self.logger.error(f"发送心跳消息失败: {e}")
            return False

    def get_connection_status(self) -> Dict[str, Any]:
        """获取连接状态"""
        if self.is_main_server:
            return {
                "mode": "main_server",
                "is_running": self.is_running,
                "client_count": len(self.client_connections),
                "clients": list(self.client_connections.keys())
            }
        else:
            return {
                "mode": "sub_server",
                "is_running": self.is_running,
                "is_connected": self.is_connected,
                "server_address": f"{self.config.main_server_host}:{self.config.main_server_port}" if self.config else "未配置"
            }


# 全局网络管理器实例
network_manager = NetworkManager()
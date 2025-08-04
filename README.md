# MCDR-ChatSync
一个将你所有的mcdr服务器消息+QQ群消息全部同步的插件

当你在一个mcdr服务器内发送信息/触发死亡或成就等事件时，其他mcdr服务器和QQ群内的用户都能同步看到
当你在QQ群内发送信息时，所有mcdr服务器内的用户也都能看到

**与QQ群同步消息的功能正在开发中~**

# 使用方法
## 一键安装（推荐）
0. 在你的一堆mcdr服务器中任意选择一个作为主服务器，主服务器要一直处于启动状态才能使消息同步服务正常运行
1. 启动mcdreforged，运行指令 `!!MCDR plugin install mg_events`
2. 按照下方说明修改 `config\chat_sync\config.json` 中的配置
3. 重启mcdreforged或重载插件

## 手动安装
0. 在你的一堆mcdr服务器中任意选择一个作为主服务器，主服务器要一直处于启动状态才能使消息同步服务正常运行
1. 在 [release](https://github.com/sedatemickey/MCDR-ChatSync/releases) 中下载最新版本的插件，放到 `plugins` 文件夹内
2. 安装前置插件 [online_player_api](https://mcdreforged.com/zh-CN/plugin/online_player_api) 和 [mg_events](https://mcdreforged.com/zh-CN/plugin/mg_events)
3. 运行一次mcdreforged，生成配置文件
4. 按照下方说明修改 `config\chat_sync\config.json` 中的配置
5. 重启mcdreforged或重载插件

# 配置文件说明
~~没标注释的地方还在开发中，暂时不用管~~
```json
{
    "main_server": true, // 是否为主服务器
    "main_server_host": "127.0.0.1", // 主服务器IP地址
    "main_server_port": 29530, // 主服务器端口
    "main_server_password": "123", // 主服务器连接秘钥，请自己设置，所有服务器必须相同
    "qq_bot_enabled": false, // 是否启用QQ机器人功能
    "onebot_ws_host": "127.0.0.1", // WebSocket 服务器地址
    "onebot_ws_port": 8080, // WebSocket 服务器端口
    "onebot_access_token": "", // WebSocket 访问令牌（可选）
    "qq_group_id": [123456, 234567], // 要同步的QQ群ID，多个群用逗号分隔
    "mc_server_name": "我的mc服务器", // 该服务器名称，用于在消息中显示
    "mc_chat_format": "[{server}] <{player}> {message}", // mc中同步玩家聊天消息的格式
    "mc_event_format": "[{server}] {message}", // mc中同步事件消息的格式
    "qq_chat_format": "[{server}] <{player}> {message}",
    "qq_event_format": "[{server}] {message}",
    "sync_mc_to_qq": true,
    "sync_qq_to_mc": true,
    "sync_mc_to_mc": true,
    "sync_qq_to_qq": true,
    "sync_player_join_leave": true, // 是否同步玩家加入/离开事件
    "sync_player_death": true, // 是否同步玩家死亡事件
    "sync_player_advancement": true, // 是否同步玩家成就事件
    "filter_commands": true, // 是否开启消息过滤功能
    "filter_prefixes": [ // 过滤包含下列任意前缀的消息
        "/",
        "!",
        ".",
        "#"
    ],
    "max_message_length": 200 // 最大允许转发的消息长度
}
```

# QQ机器人框架 连接说明

本插件使用Onebot协议，WebSocket 服务器模式，ChatSync作为 WebSocket 服务器，QQ机器人框架作为客户端连接

## 连接地址
- WebSocket 地址：`ws://127.0.0.1:8080/onebot/v11/ws`
- 如果设置了Websocket访问令牌，需要在QQ机器人框架里配置相同令牌


# TODO
- [x] 添加对QQ群消息同步的支持
- [ ] 使用心跳信息维持连接
- [ ] 支持MCDR指令
- [ ] 优化配置文件
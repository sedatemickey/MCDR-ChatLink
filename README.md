# MCDR-ChatLink
一个将你所有的mcdr服务器消息+QQ群消息全部同步的插件

当你在一个mcdr服务器内发送信息/触发死亡或成就等事件时，其他mcdr服务器和QQ群内的用户都能同步看到
当你在QQ群内发送信息时，所有mcdr服务器内的用户也都能看到

**与QQ群同步消息的功能正在开发中~**

# 使用方法
0. 在你的一堆mcdr服务器中任意选择一个主服务器，主服务器要一直处于启动状态才能使消息同步服务正常运行
1. 在[release](https://github.com/sedatemickey/MCDR-ChatLink/releases)中下载最新版本的插件
2. 将插件放到 `plugins` 文件夹内
3. 运行一次mcdreforged，生成配置文件
4. 按照下方说明修改 `config\chat_link\config.json` 中的配置
5. 重启mcdreforged或重载插件

# 配置文件说明
~~没标注释的地方还在开发中，暂时不用管~~
```json
{
    "main_server": true, // 是否为主服务器
    "main_server_host": "127.0.0.1", // 主服务器IP地址
    "main_server_port": 29530, // 主服务器端口
    "main_server_password": "123", // 主服务器连接秘钥，请自己设置，所有服务器必须相同
    "qq_bot_enabled": false,
    "onebot_api_host": "127.0.0.1",
    "onebot_api_port": 8080,
    "qq_group_id": [],
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
    "filter_commands": true,
    "filter_prefixes": [
        "/",
        "!",
        ".",
        "#"
    ],
    "max_message_length": 200
}
```

# TODO
- [ ] 添加对QQ群消息同步的支持
- [ ] 使用心跳信息维持连接
- [ ] 支持MCDR指令
- [ ] 优化配置文件
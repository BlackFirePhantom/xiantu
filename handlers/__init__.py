"""handlers 包主入口，用于初始化和注册所有的 SocketIO 事件处理器。"""

import game_state

def init_handlers(socketio):
    # 注入全局 SocketIO 引用，使得其他业务模块可以跨文件发送广播消息
    game_state.socketio = socketio

    # 延迟导入子处理器，防止在包级别发生提早加载引起的循环依赖
    from .base import register_base_handlers
    from .gameplay import register_gameplay_handlers
    from .combat import register_combat_handlers
    from .cultivation import register_cultivation_handlers
    from .items import register_items_handlers
    from .pets import register_pets_handlers
    from .adventure import register_adventure_handlers
    from .npc import register_npc_handlers
    from .auction import register_auction_handlers
    from .secret_realm import register_secret_realm_handlers
    from .sect_boss import register_sect_boss_handlers

    # 注册所有 Socket 路由与事件监听
    register_base_handlers(socketio)
    register_gameplay_handlers(socketio)
    register_combat_handlers(socketio)
    register_cultivation_handlers(socketio)
    register_items_handlers(socketio)
    register_pets_handlers(socketio)
    register_adventure_handlers(socketio)
    register_npc_handlers(socketio)
    register_auction_handlers(socketio)
    register_secret_realm_handlers(socketio)
    register_sect_boss_handlers(socketio)

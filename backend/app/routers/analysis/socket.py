# ruff: noqa: F401,F403,F405,F821
@router.websocket("/ws/task/{task_id}")
async def websocket_task_progress(websocket: WebSocket, task_id: str):
    """WebSocket 端点：实时获取任务进度"""
    json = importlib.import_module("json")
    websocket_manager = get_websocket_manager()

    try:
        await websocket_manager.connect(websocket, task_id)

        # 发送连接确认消息
        await websocket.send_text(
            json.dumps(
                {
                    "type": "connection_established",
                    "task_id": task_id,
                    "message": "WebSocket 连接已建立",
                }
            )
        )

        # 保持连接活跃
        while True:
            try:
                # 接收客户端的心跳消息
                data = await websocket.receive_text()
                # 可以处理客户端发送的消息
                logger.debug(f"📡 收到 WebSocket 消息: {data}")
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.warning(f"⚠️ WebSocket 消息处理错误: {e}")
                break

    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket 客户端断开连接: {task_id}")
    except Exception as e:
        logger.error(f"❌ WebSocket 连接错误: {e}")
    finally:
        await websocket_manager.disconnect(websocket, task_id)

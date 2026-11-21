# -*- coding: utf-8 -*-
"""会话管理接口：获取历史 / 清除会话（需登录，仅限本人会话）"""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.schemas import ConversationListResponse, ConversationResponse, DeleteResponse
from app.models.user import User
from app.storage.session_store import get_session_store

router = APIRouter(prefix="/api/conversations", tags=["会话"])


@router.get("", response_model=ConversationListResponse, summary="获取会话列表")
async def list_conversations(current: User = Depends(get_current_user)) -> ConversationListResponse:
    """返回当前用户的全部会话（按更新时间倒序），用于历史对话列表"""
    store = get_session_store()
    sessions = store.list_sessions(user_id=current.id)
    return ConversationListResponse(sessions=sessions)


@router.get("/{session_id}", response_model=ConversationResponse, summary="获取会话历史")
async def get_conversation(session_id: str, current: User = Depends(get_current_user)) -> ConversationResponse:
    store = get_session_store()
    messages = store.get_messages(session_id, user_id=current.id)
    meta = store.get_meta(session_id, user_id=current.id)
    return ConversationResponse(
        session_id=session_id,
        messages=[{"role": m["role"], "content": m["content"], "timestamp": m["timestamp"],
                   "extra": m.get("extra")} for m in messages],
        created_at=meta.get("created_at"),
        updated_at=meta.get("updated_at"),
    )


@router.delete("/{session_id}", response_model=DeleteResponse, summary="清除会话")
async def delete_conversation(session_id: str, current: User = Depends(get_current_user)) -> DeleteResponse:
    get_session_store().clear(session_id, user_id=current.id)
    return DeleteResponse(session_id=session_id, deleted=True, message="会话已清除")

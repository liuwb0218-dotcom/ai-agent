# -*- coding: utf-8 -*-
"""管理员接口：知识库文档管理（列表 / 上传 / 删除）"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.deps import require_admin
from app.models.user import User
from app.services.local_rag import local_rag_service

router = APIRouter(prefix="/api/admin/knowledge", tags=["管理"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5MB


@router.get("/documents", summary="知识库文档列表")
def list_documents(_: User = Depends(require_admin)) -> dict:
    documents = local_rag_service.list_documents()
    return {"total": len(documents), "documents": documents}


@router.post("/documents", status_code=201, summary="上传知识文档（md/txt/docx）")
async def upload_document(file: UploadFile = File(...), _: User = Depends(require_admin)) -> dict:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="文件内容为空")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="文件过大，最大 5MB")
    try:
        return local_rag_service.import_document(file.filename or "untitled.md", data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/documents/{doc_id}", summary="删除知识文档")
def delete_document(doc_id: str, _: User = Depends(require_admin)) -> dict:
    if not local_rag_service.delete_document(doc_id):
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"message": "文档已删除"}

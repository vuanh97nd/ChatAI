"""Local API routes; optional bearer token for a deliberately exposed service."""
import secrets
import asyncio
from typing import Annotated, Any
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from .schemas import JobRequest, DocumentIndex

router = APIRouter(prefix='/plaxis', tags=['PLAXIS'])


def authorized(request: Request, authorization: Annotated[str | None, Header()] = None) -> None:
    token = request.app.state.api_token
    if token and not secrets.compare_digest(authorization or '', 'Bearer ' + token):
        raise HTTPException(401, 'Bearer token không hợp lệ.')


@router.post('/jobs', status_code=202, dependencies=[Depends(authorized)])
async def submit(request: Request, payload: JobRequest) -> dict[str, str]:
    try:
        job = request.app.state.jobs.submit(payload)
    except RuntimeError as error:
        raise HTTPException(429, str(error)) from error
    return {'id': job.id, 'status': job.status}


@router.get('/jobs/{job_id}', dependencies=[Depends(authorized)])
async def inspect(request: Request, job_id: str) -> dict[str, Any]:
    job = request.app.state.jobs.jobs.get(job_id)
    if job is None:
        raise HTTPException(404, 'Không tìm thấy công việc; lịch sử API chỉ giữ trong tiến trình này.')
    return job.public()


@router.post('/jobs/{job_id}/stop', dependencies=[Depends(authorized)])
async def stop(request: Request, job_id: str) -> dict[str, str]:
    job = request.app.state.jobs.jobs.get(job_id)
    if job is None:
        raise HTTPException(404, 'Không tìm thấy công việc.')
    if job.status in {'queued', 'running', 'stopping'}:
        job.stop.set()
        job.status = 'stopping'
    return {'id': job.id, 'status': job.status,
            'note': 'Dừng trước bước tiếp theo; không hủy giả thao tác PLAXIS đang thực hiện.'}


@router.post('/documents/index', dependencies=[Depends(authorized)])
async def index_document(request: Request, payload: DocumentIndex) -> dict[str, Any]:
    knowledge = request.app.state.jobs.knowledge
    if knowledge is None:
        raise HTTPException(409, 'Cần cấu hình CHATAI_AGENT_DOCUMENT_ROOTS và cài requirements-rag.txt.')
    def index():
        return knowledge.commit(knowledge.prepare(payload.path))
    try:
        return await asyncio.to_thread(index)
    except (ValueError, PermissionError, FileNotFoundError) as error:
        raise HTTPException(422, str(error)) from error

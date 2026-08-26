
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from services.model_training.monitoring.gpu_monitor import read_gpu_metrics

router = APIRouter(prefix='/api/training/monitoring', tags=['monitoring'])

@router.get('/gpu')
def gpu(): return {'gpus': read_gpu_metrics()}

@router.websocket('/ws/{job_id}')
async def training_ws(websocket: WebSocket, job_id: int):
    await websocket.accept()
    try:
        while True:
            await websocket.send_json({'job_id': job_id, 'gpu': read_gpu_metrics()})
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return

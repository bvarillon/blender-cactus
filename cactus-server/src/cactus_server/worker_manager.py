"""Manager for worker connections and status."""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set
from uuid import UUID

from cactus_tools.schemas import (
    WorkerInfo,
    WorkerStatusMessage,
    WorkerDeregisterMessage,
    MessageType,
)

logger = logging.getLogger(__name__)


class WorkerConnection:
    """Represents a connected worker."""
    
    def __init__(self, worker_id: UUID, websocket, worker_info: WorkerInfo):
        self.worker_id = worker_id
        self.websocket = websocket
        self.worker_info = worker_info
        self.connected_at = datetime.utcnow()
        self.last_ping = datetime.utcnow()
        self.current_task_id: Optional[UUID] = None
        self.status = "idle"
        self.is_active = True
    
    async def send_message(self, message: str) -> bool:
        """Send a message to the worker."""
        try:
            await self.websocket.send_text(message)
            self.last_ping = datetime.utcnow()
            return True
        except Exception as e:
            logger.error(f"Failed to send message to worker {self.worker_id}: {e}")
            self.is_active = False
            return False
    
    async def close(self) -> None:
        """Close the connection."""
        try:
            await self.websocket.close()
        except Exception as e:
            logger.error(f"Error closing worker {self.worker_id} connection: {e}")
        self.is_active = False
    
    def update_status(self, status: str, task_id: Optional[UUID] = None) -> None:
        """Update worker status."""
        self.status = status
        self.current_task_id = task_id
        self.last_ping = datetime.utcnow()


class WorkerManager:
    """Manages all connected workers."""
    
    def __init__(self, max_workers: int = 100, worker_timeout: int = 300):
        self.max_workers = max_workers
        self.worker_timeout = worker_timeout
        self.workers: Dict[UUID, WorkerConnection] = {}
        self.worker_lock = asyncio.Lock()
        self.worker_by_status: Dict[str, Set[UUID]] = {
            "idle": set(),
            "processing": set(),
            "offline": set(),
        }
    
    async def register_worker(
        self, worker_id: UUID, websocket, worker_info: WorkerInfo
    ) -> bool:
        """Register a new worker."""
        async with self.worker_lock:
            if len(self.workers) >= self.max_workers:
                logger.warning(f"Maximum workers reached ({self.max_workers})")
                return False
            
            if worker_id in self.workers:
                logger.warning(f"Worker {worker_id} already registered")
                # Update existing worker
                await self.deregister_worker(worker_id)
            
            connection = WorkerConnection(worker_id, websocket, worker_info)
            self.workers[worker_id] = connection
            self.worker_by_status["idle"].add(worker_id)
            
            logger.info(f"Worker {worker_id} registered: {worker_info.name}")
            return True
    
    async def deregister_worker(self, worker_id: UUID, reason: Optional[str] = None) -> bool:
        """Deregister a worker."""
        async with self.worker_lock:
            if worker_id not in self.workers:
                return False
            
            worker = self.workers[worker_id]
            await worker.close()
            
            # Remove from status tracking
            for status, worker_ids in self.worker_by_status.items():
                if worker_id in worker_ids:
                    worker_ids.remove(worker_id)
                    break
            
            self.worker_by_status["offline"].add(worker_id)
            del self.workers[worker_id]
            
            logger.info(f"Worker {worker_id} deregistered: {reason or 'unknown reason'}")
            return True
    
    async def update_worker_status(
        self, worker_id: UUID, status: str, task_id: Optional[UUID] = None
    ) -> bool:
        """Update a worker's status."""
        async with self.worker_lock:
            if worker_id not in self.workers:
                return False
            
            # Remove from old status
            old_status = self.workers[worker_id].status
            if old_status in self.worker_by_status:
                self.worker_by_status[old_status].discard(worker_id)
            
            # Update worker
            self.workers[worker_id].update_status(status, task_id)
            
            # Add to new status
            if status not in self.worker_by_status:
                self.worker_by_status[status] = set()
            self.worker_by_status[status].add(worker_id)
            
            return True
    
    def get_worker(self, worker_id: UUID) -> Optional[WorkerConnection]:
        """Get a worker by ID."""
        return self.workers.get(worker_id)
    
    def get_idle_workers(self) -> List[WorkerConnection]:
        """Get all idle workers."""
        return [self.workers[wid] for wid in self.worker_by_status.get("idle", set()) if wid in self.workers]
    
    def get_processing_workers(self) -> List[WorkerConnection]:
        """Get all workers currently processing tasks."""
        return [self.workers[wid] for wid in self.worker_by_status.get("processing", set()) if wid in self.workers]
    
    def get_all_workers(self) -> List[WorkerConnection]:
        """Get all connected workers."""
        return list(self.workers.values())
    
    def get_worker_count(self) -> int:
        """Get the number of connected workers."""
        return len(self.workers)
    
    def get_worker_ids_by_status(self, status: str) -> Set[UUID]:
        """Get worker IDs by status."""
        return self.worker_by_status.get(status, set()).copy()
    
    async def check_timeout_workers(self) -> List[UUID]:
        """Check for workers that have timed out."""
        from datetime import datetime, timedelta
        
        timed_out = []
        timeout_delta = timedelta(seconds=self.worker_timeout)
        
        async with self.worker_lock:
            for worker_id, worker in list(self.workers.items()):
                if datetime.utcnow() - worker.last_ping > timeout_delta:
                    timed_out.append(worker_id)
        
        return timed_out
    
    async def cleanup_inactive_workers(self) -> int:
        """Clean up inactive workers."""
        timed_out = await self.check_timeout_workers()
        
        for worker_id in timed_out:
            await self.deregister_worker(worker_id, reason="timeout")
        
        return len(timed_out)
    
    def get_worker_summary(self, worker_id: UUID) -> Optional[Dict]:
        """Get a summary of a worker's status."""
        worker = self.get_worker(worker_id)
        if not worker:
            return None
        
        return {
            "worker_id": worker.worker_id,
            "name": worker.worker_info.name,
            "status": worker.status,
            "current_task_id": worker.current_task_id,
            "connected_at": worker.connected_at.isoformat(),
            "last_ping": worker.last_ping.isoformat(),
        }
    
    def get_all_workers_summary(self) -> List[Dict]:
        """Get summaries for all workers."""
        return [self.get_worker_summary(wid) for wid in self.workers.keys() if self.get_worker_summary(wid)]

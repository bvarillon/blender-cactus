"""Queue for managing render tasks."""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Deque, Tuple
from collections import deque
from uuid import UUID

from cactus_tools.schemas import (
    RenderTask,
    ProjectInfo,
    TaskStatus,
    MessageType,
)

logger = logging.getLogger(__name__)


class TaskQueue:
    """Manages the queue of render tasks."""
    
    def __init__(self, max_queue_size: int = 1000):
        self.max_queue_size = max_queue_size
        self.queue: Deque[RenderTask] = deque()
        self.tasks: Dict[UUID, RenderTask] = {}
        self.project_tasks: Dict[UUID, List[UUID]] = {}  # project_id -> list of task_ids
        self.queue_lock = asyncio.Lock()
        self.task_status: Dict[UUID, TaskStatus] = {}
    
    async def add_task(self, task: RenderTask) -> bool:
        """Add a new task to the queue."""
        async with self.queue_lock:
            if len(self.queue) >= self.max_queue_size:
                logger.warning(f"Task queue full ({self.max_queue_size})")
                return False
            
            if task.task_id in self.tasks:
                logger.warning(f"Task {task.task_id} already exists")
                return False
            
            self.tasks[task.task_id] = task
            self.queue.append(task)
            self.task_status[task.task_id] = task.status
            
            # Track project tasks
            if task.project_id not in self.project_tasks:
                self.project_tasks[task.project_id] = []
            self.project_tasks[task.project_id].append(task.task_id)
            
            logger.info(f"Added task {task.task_id} for project {task.project_id}, frame {task.frame_number}")
            return True
    
    async def add_project_tasks(
        self, project_info: ProjectInfo, num_frames: Optional[int] = None
    ) -> List[RenderTask]:
        """Add all tasks for a project to the queue."""
        created_tasks = []
        
        frame_start = project_info.frame_start
        frame_end = project_info.frame_end
        frame_step = project_info.frame_step
        
        if num_frames is not None:
            frame_end = frame_start + num_frames - 1
        
        for frame in range(frame_start, frame_end + 1, frame_step):
            task = RenderTask(
                task_id=UUID(int=0),  # Will be regenerated
                project_id=project_info.project_id,
                frame_number=frame,
                status=TaskStatus.PENDING,
            )
            # Generate a proper UUID
            task.task_id = UUID(int=0)
            created_tasks.append(task)
        
        # Add all tasks
        for task in created_tasks:
            await self.add_task(task)
        
        return created_tasks
    
    async def get_next_task(self) -> Optional[RenderTask]:
        """Get the next task from the queue."""
        async with self.queue_lock:
            if not self.queue:
                return None
            
            task = self.queue.popleft()
            return task
    
    async def assign_task(self, task_id: UUID, worker_id: UUID) -> bool:
        """Assign a task to a worker."""
        async with self.queue_lock:
            if task_id not in self.tasks:
                return False
            
            task = self.tasks[task_id]
            task.assigned_worker_id = worker_id
            task.status = TaskStatus.ASSIGNED
            task.started_at = datetime.utcnow()
            self.task_status[task_id] = TaskStatus.ASSIGNED
            
            logger.info(f"Assigned task {task_id} to worker {worker_id}")
            return True
    
    async def update_task_status(
        self, task_id: UUID, status: TaskStatus, worker_id: Optional[UUID] = None
    ) -> bool:
        """Update the status of a task."""
        async with self.queue_lock:
            if task_id not in self.tasks:
                return False
            
            task = self.tasks[task_id]
            task.status = status
            self.task_status[task_id] = status
            
            if status == TaskStatus.PROCESSING:
                task.started_at = datetime.utcnow()
            elif status == TaskStatus.COMPLETED:
                task.completed_at = datetime.utcnow()
            elif status == TaskStatus.FAILED:
                task.completed_at = datetime.utcnow()
            
            logger.info(f"Task {task_id} status updated to {status}")
            return True
    
    async def complete_task(
        self, task_id: UUID, output_file: Optional[str] = None, render_time: Optional[float] = None
    ) -> bool:
        """Mark a task as completed."""
        async with self.queue_lock:
            if task_id not in self.tasks:
                return False
            
            task = self.tasks[task_id]
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            task.output_file = output_file
            task.render_time_seconds = render_time
            self.task_status[task_id] = TaskStatus.COMPLETED
            
            logger.info(f"Task {task_id} completed")
            return True
    
    async def fail_task(self, task_id: UUID, error_message: str) -> bool:
        """Mark a task as failed."""
        async with self.queue_lock:
            if task_id not in self.tasks:
                return False
            
            task = self.tasks[task_id]
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.utcnow()
            task.error_message = error_message
            self.task_status[task_id] = TaskStatus.FAILED
            
            logger.info(f"Task {task_id} failed: {error_message}")
            return True
    
    def get_task(self, task_id: UUID) -> Optional[RenderTask]:
        """Get a task by ID."""
        return self.tasks.get(task_id)
    
    def get_tasks_by_project(self, project_id: UUID) -> List[RenderTask]:
        """Get all tasks for a project."""
        task_ids = self.project_tasks.get(project_id, [])
        return [self.tasks[tid] for tid in task_ids if tid in self.tasks]
    
    def get_pending_tasks(self) -> List[RenderTask]:
        """Get all pending tasks."""
        return [t for t in self.tasks.values() if t.status == TaskStatus.PENDING]
    
    def get_assigned_tasks(self) -> List[RenderTask]:
        """Get all assigned tasks."""
        return [t for t in self.tasks.values() if t.status == TaskStatus.ASSIGNED]
    
    def get_processing_tasks(self) -> List[RenderTask]:
        """Get all tasks currently being processed."""
        return [t for t in self.tasks.values() if t.status == TaskStatus.PROCESSING]
    
    def get_completed_tasks(self) -> List[RenderTask]:
        """Get all completed tasks."""
        return [t for t in self.tasks.values() if t.status == TaskStatus.COMPLETED]
    
    def get_failed_tasks(self) -> List[RenderTask]:
        """Get all failed tasks."""
        return [t for t in self.tasks.values() if t.status == TaskStatus.FAILED]
    
    def get_queue_size(self) -> int:
        """Get the current queue size."""
        return len(self.queue)
    
    def get_total_tasks(self) -> int:
        """Get the total number of tasks."""
        return len(self.tasks)
    
    def get_task_counts_by_status(self) -> Dict[TaskStatus, int]:
        """Get counts of tasks by status."""
        counts = {s: 0 for s in TaskStatus}
        for task in self.tasks.values():
            counts[task.status] += 1
        return counts
    
    async def cancel_project_tasks(self, project_id: UUID) -> int:
        """Cancel all tasks for a project."""
        task_ids = self.project_tasks.get(project_id, [])
        cancelled_count = 0
        
        async with self.queue_lock:
            for task_id in task_ids:
                if task_id in self.tasks:
                    task = self.tasks[task_id]
                    if task.status in [TaskStatus.PENDING, TaskStatus.ASSIGNED]:
                        task.status = TaskStatus.CANCELLED
                        self.task_status[task_id] = TaskStatus.CANCELLED
                        cancelled_count += 1
        
        logger.info(f"Cancelled {cancelled_count} tasks for project {project_id}")
        return cancelled_count
    
    def get_task_summary(self, task_id: UUID) -> Optional[Dict]:
        """Get a summary of a task."""
        task = self.get_task(task_id)
        if not task:
            return None
        
        return {
            "task_id": task.task_id,
            "project_id": task.project_id,
            "frame_number": task.frame_number,
            "status": task.status.value,
            "assigned_worker_id": task.assigned_worker_id,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        }

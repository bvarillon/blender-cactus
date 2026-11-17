"""Blender renderer for Cactus worker."""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from uuid import UUID

from cactus_tools.schemas import RenderTask, ProjectInfo, TaskStatus

logger = logging.getLogger(__name__)


class BlenderRenderError(Exception):
    """Exception raised when Blender rendering fails."""
    pass


class BlenderRenderer:
    """Handles rendering of Blender files."""
    
    def __init__(
        self,
        blender_path: str = "blender",
        temp_dir: str = "/tmp/cactus",
        output_dir: str = "/output/cactus",
    ):
        self.blender_path = blender_path
        self.temp_dir = Path(temp_dir)
        self.output_dir = Path(output_dir)
        
        # Create directories if they don't exist
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    async def render_task(
        self, task: RenderTask, project_info: ProjectInfo
    ) -> Dict[str, Any]:
        """Render a single task (frame)."""
        start_time = datetime.utcnow()
        
        try:
            # Prepare render command
            output_path = self._get_output_path(task, project_info)
            
            # Build Blender command
            cmd = self._build_blender_command(task, project_info, output_path)
            
            logger.info(f"Starting render for task {task.task_id}, frame {task.frame_number}")
            logger.debug(f"Blender command: {' '.join(cmd)}")
            
            # Run Blender
            result = await self._run_blender_command(cmd)
            
            end_time = datetime.utcnow()
            render_time = (end_time - start_time).total_seconds()
            
            if result["success"]:
                logger.info(f"Render completed for task {task.task_id} in {render_time:.2f}s")
                return {
                    "status": TaskStatus.COMPLETED,
                    "output_file": str(output_path),
                    "render_time_seconds": render_time,
                    "frame_number": task.frame_number,
                    "task_id": task.task_id,
                }
            else:
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Render failed for task {task.task_id}: {error_msg}")
                return {
                    "status": TaskStatus.FAILED,
                    "error_message": error_msg,
                    "render_time_seconds": render_time,
                    "frame_number": task.frame_number,
                    "task_id": task.task_id,
                }
                
        except Exception as e:
            end_time = datetime.utcnow()
            render_time = (end_time - start_time).total_seconds()
            logger.error(f"Render error for task {task.task_id}: {str(e)}")
            return {
                "status": TaskStatus.FAILED,
                "error_message": str(e),
                "render_time_seconds": render_time,
                "frame_number": task.frame_number,
                "task_id": task.task_id,
            }
    
    def _get_output_path(self, task: RenderTask, project_info: ProjectInfo) -> Path:
        """Get the output path for a rendered frame."""
        project_output_dir = self.output_dir / str(project_info.project_id)
        project_output_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"frame_{task.frame_number:04d}.png"
        return project_output_dir / filename
    
    def _build_blender_command(
        self, task: RenderTask, project_info: ProjectInfo, output_path: Path
    ) -> list:
        """Build the Blender command for rendering."""
        cmd = [
            self.blender_path,
            project_info.blender_file_path,
            "--background",
            "--render-frame", str(task.frame_number),
            "--output", str(output_path),
            "--render-engine", project_info.render_engine,
        ]
        
        # Add GPU/CPU settings
        if project_info.use_gpu:
            cmd.extend(["--use-gpu"])
        
        # Add resolution
        cmd.extend([
            "--render-resolution",
            f"{project_info.resolution_x}x{project_info.resolution_y}",
        ])
        
        # Add samples
        cmd.extend(["--render-samples", str(project_info.samples)])
        
        # Add threads (use all available)
        import os
        cpu_count = os.cpu_count() or 1
        cmd.extend(["--threads", str(cpu_count)])
        
        return cmd
    
    async def _run_blender_command(self, cmd: list) -> Dict[str, Any]:
        """Run a Blender command asynchronously."""
        process = None
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            
            # Read output in real-time
            stdout_lines = []
            stderr_lines = []
            
            async def read_stream(stream, lines):
                while True:
                    line = await asyncio.get_event_loop().run_in_executor(
                        None, stream.readline
                    )
                    if not line:
                        break
                    lines.append(line.strip())
                    logger.debug(f"Blender: {line.strip()}")
            
            # Read stdout and stderr concurrently
            await asyncio.gather(
                read_stream(process.stdout, stdout_lines),
                read_stream(process.stderr, stderr_lines),
            )
            
            return_code = await asyncio.get_event_loop().run_in_executor(
                None, process.wait
            )
            
            if return_code == 0:
                return {"success": True, "output": "\n".join(stdout_lines)}
            else:
                error = "\n".join(stderr_lines) or "Blender exited with non-zero code"
                return {"success": False, "error": error, "return_code": return_code}
                
        except FileNotFoundError as e:
            return {"success": False, "error": f"Blender not found: {self.blender_path}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if process:
                process.stdout.close()
                process.stderr.close()
    
    async def validate_blender(self) -> bool:
        """Validate that Blender is installed and accessible."""
        try:
            result = await self._run_blender_command([self.blender_path, "--version"])
            return result["success"]
        except Exception:
            return False
    
    def get_blender_version(self) -> Optional[str]:
        """Get the Blender version."""
        try:
            import subprocess
            result = subprocess.run(
                [self.blender_path, "--version"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "Blender" in line and "version" in line.lower():
                        return line.strip()
            return None
        except Exception:
            return None

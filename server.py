import json
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from src.agent import TerminalAgent

app = FastAPI()

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = TerminalAgent()

@app.post("/run")
async def run_task(request: Request):
    data = await request.json()
    task = data.get("task")
    cwd = data.get("cwd")
    
    if not task:
        return {"error": "No task provided"}

    async def event_generator():
        # run_generator is a synchronous generator, we wrap it in a thread or just run it
        # Since it's blocking, we run it in a thread to keep the event loop free
        loop = asyncio.get_event_loop()
        
        def get_events():
            return agent.run_generator(task, cwd=cwd)
            
        events = await loop.run_in_executor(None, get_events)
        
        for event in events:
            yield f"data: {json.dumps(event)}\n\n"
            await asyncio.sleep(0.1) # Small delay for UI smoothness

    return StreamingResponse(event_generator(), media_type="text/event-stream")

from pydantic import BaseModel
import sys
import os
import subprocess
import time

class FileExecuteRequest(BaseModel):
    path: str
    action: str  # 'run' or 'compile'

@app.post("/execute_file")
async def execute_file(request: FileExecuteRequest):
    path = request.path
    action = request.action
    
    if not os.path.exists(path):
        return {"error": f"File not found: {path}"}
        
    start_time = time.time()
    
    if action == "compile":
        # Compile python file to check for syntax errors
        cmd = [sys.executable, "-m", "py_compile", path]
    else:
        # Run python file
        cmd = [sys.executable, path]
        
    try:
        # Run the subprocess synchronously in an executor to avoid blocking the event loop
        def run_proc():
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
        loop = asyncio.get_event_loop()
        process = await loop.run_in_executor(None, run_proc)
        
        duration = time.time() - start_time
        return {
            "stdout": process.stdout,
            "stderr": process.stderr,
            "exit_code": process.returncode,
            "duration": duration,
            "success": process.returncode == 0
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": "Execution timed out after 30 seconds.",
            "exit_code": -1,
            "duration": 30.0,
            "success": False
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": str(e),
            "exit_code": 1,
            "duration": 0.0,
            "success": False
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

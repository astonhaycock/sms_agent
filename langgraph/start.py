# start the agent router uv run uvicorn agent_router.agent_router:app --host 0.0.0.0 --port 8000
import uvicorn
from agent_router.agent_router import app

if __name__ == "__main__":
    # allow entire network to access the agent router
    ip_address = "192.168.1.23"
    print(f"Agent router is running on {ip_address}:3002")
    uvicorn.run("agent_router.agent_router:app", host=ip_address, port=3002, reload=True)

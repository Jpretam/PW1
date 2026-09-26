import httpx
import time
import json
import asyncio

async def test_code():
    code = """def calculate(x):
    return 10 / x

def process():
    value = 0
    return calculate(value)

process()"""

    async with httpx.AsyncClient(timeout=120) as client:
        # 1. Execute the code to generate an execution_id
        res = await client.post("http://127.0.0.1:8000/execute", json={
            "language": "python",
            "code": code
        })
        res.raise_for_status()
        exec_data = res.json()
        execution_id = exec_data.get("execution_id")
        print(f"Executed code. Execution ID: {execution_id}")

        if not execution_id:
            return

        # 2. Wait a moment
        await asyncio.sleep(1)

        # 3. Call debug endpoint which runs ContextCurator under the hood
        print(f"Debugging execution {execution_id}...")
        res_debug = await client.post("http://127.0.0.1:8000/debug/fix", json={
            "execution_id": execution_id
        })
        res_debug.raise_for_status()
        debug_data = res_debug.json()
        
        print("\n--- FINAL DEBUG RESULT ---")
        print(json.dumps(debug_data, indent=2))

if __name__ == "__main__":
    asyncio.run(test_code())

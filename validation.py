import os
import aiohttp
import json
import aiofiles


NETBOX_URL = os.environ.get("NETBOX_URL") or "http://netbox:8080/"

async def get_schema():
    # Try to read from local schema.json file first
    try:
        async with aiofiles.open("schema.json", "r") as f:
            content = await f.read()
            return json.loads(content)
    except FileNotFoundError:
        # If file doesn't exist, make the HTTP request
        headers = {
            "Accept": "application/json",
        }
        url = f"{NETBOX_URL.rstrip('/')}/api/schema/"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                schema_data = await response.json()
                
                # Save the schema to file for future use
                async with aiofiles.open("schema.json", "w") as f:
                    await f.write(json.dumps(schema_data, indent=2))
                
                return schema_data

async def validate_path(schema, path):
    schema_paths = schema.get("paths", {}).keys()
    if path not in schema_paths:
        raise ValueError(f"Path '{path}' does not exist\navailable paths: {list(schema_paths)}")
    
async def validate_query_params(schema, path, query_params):
    schema_params = schema.get("paths", {}).get(path, {}).get("get", {}).get("parameters", [])
    valid_params = {param["name"] for param in schema_params}
    invalid_params = [param for param in query_params.keys() if param not in valid_params]
    if invalid_params:
        raise ValueError(f"Invalid query parameters: {invalid_params}\navailable parameters: {list(valid_params)}")
    
    


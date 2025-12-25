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
    model_assesors = ['site', 'manufacturer', 'cluster_group', 'device_type',
                       'device','tenant',  'contact', 'group', 'role', 'platform', 'location',
                       'rack', 'region', 'type', 'provider', 'circuit', 'virtual_circuit',
                       'power_panel', 'power_port', 'power_feed', 'module_type', 'module',
                       'interface', 'front_port', 'rear_port', 'console_port', 'console_server_port',
                       'cluster', 'virtual_device_context', 'vrf', 'vlan', 'prefix', 'aggregate',
                       'asn', 'asn_range', 'fhrp_group', 'ip_address', 'ip_range',
                       'service', 'device_role', 'rack_role', 
                       'circuit_type', 'virtual_circuit_type',]
    not_validated_fields = {}
    validated_fields = {}
    params = query_params.copy()
    for field in params:
        assessors = field.split("__")
        if len(assessors) >= 3:
            raise ValueError("Only one level of field lookup is supported, e.g., 'site__slug'")
        if len(assessors) == 2:
            if assessors[1] in model_assesors:
                not_validated_fields[field] = params[field]
            else:
                validated_fields[field] = params[field]
        else:
            validated_fields[field] = params[field]
    schema_params = schema.get("paths", {}).get(path, {}).get("get", {}).get("parameters", [])
    valid_params = {param["name"] for param in schema_params}
    invalid_params = [param for param in validated_fields.keys() if param not in valid_params]
    if invalid_params:
        raise ValueError(f"Invalid query parameters: {invalid_params}\navailable parameters: {list(valid_params)}")
    
    


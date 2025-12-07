from fastmcp import FastMCP
import netbox
import json
import logging
from typing import Annotated
from pydantic import Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create an MCP server
mcp = FastMCP(
    "NetBox",
    instructions="""Interact with NetBox to manage network infrastructure documentation. 
    
    Resources:
    - `netbox://object-types`: Returns a JSON mapping of all available NetBox object types, their API endpoints, and important fields. Read this first to understand what data is available.

    Tools:
    - `get_resource`: Fetches data from a specific NetBox endpoint. 
      - `endpoint`: The API path (e.g., 'dcim/devices'). Use the endpoints found in `netbox://object-types`.
      - `params`: A dictionary of query parameters for filtering (e.g., {'role': 'router', 'site': 'nyc'}).
    """,
    strict_input_validation=False
)

@mcp.resource("netbox://object-types")
def get_object_types() -> str:
    """Return the list of available NetBox object types and their endpoints."""
    return json.dumps(netbox.NETBOX_OBJECT_TYPES, indent=2)

@mcp.tool()
async def get_resource(
    endpoint: Annotated[str, Field(description="The NetBox API endpoint (e.g., 'dcim/devices/', 'ipam/ip-addresses/')")], 
    params: Annotated[dict, Field(description="Optional dictionary of query parameters to filter the results.")] = None,
    action: Annotated[str, Field(description="Ignored parameter")] = None,
    sessionId: Annotated[str, Field(description="Ignored parameter")] = None,
    chatInput: Annotated[str, Field(description="Ignored parameter")] = None,
    metadata: Annotated[dict, Field(description="Ignored parameter")] = None,
    toolCallId: Annotated[str, Field(description="Ignored parameter")] = None,
) -> dict:
    """
    Gather data from NetBox for a specific endpoint.
    """
    if params is None:
        params = {}

    
    
    # Find the object type definition to get the important fields
    for key, value in netbox.NETBOX_OBJECT_TYPES.items():
        if value["endpoint"] == endpoint.strip("/"):
            if "fields" in value:
                # Add the important fields to the params to guide the AI or filter results if supported
                # We use 'values' as some NetBox versions/plugins might support it, or it serves as documentation
                # But the user specifically asked to "include or replace the param fields"
                params["fields"] = value["fields"]
            break
    logger.info(f"get_resource called with endpoint: {endpoint}, params: {params}")
    return await netbox.get(endpoint, params)

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8080)

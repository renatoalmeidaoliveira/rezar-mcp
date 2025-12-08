from fastmcp import FastMCP
import netbox
import json
import logging
from typing import Annotated
from pydantic import Field

from urllib.parse import parse_qs

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
async def get_resources(
    resource: Annotated[str, Field(description="The NetBox API resource endpoint (e.g., 'dcim/devices/', 'ipam/ip-addresses/')")], 
    query_string: Annotated[str, Field(description="Optional query string to filter the results, some parameters are queried using slugs, for example use site instead of site__slug")] = None,
    action: Annotated[str, Field(description="Ignored parameter")] = None,
    sessionId: Annotated[str, Field(description="Ignored parameter")] = None,
    chatInput: Annotated[str, Field(description="Ignored parameter")] = None,
    metadata: Annotated[dict, Field(description="Ignored parameter")] = None,
    toolCallId: Annotated[str, Field(description="Ignored parameter")] = None,
) -> dict:
    """
    Gather all models matching the query from NetBox for a specific resource.
    """

    query = parse_qs(query_string) if query_string else None

    if query is None:
        query = {}

    
    
    # Find the object type definition to get the important fields
    for key, value in netbox.NETBOX_OBJECT_TYPES.items():
        if value["endpoint"] == resource.strip("/"):
            if "fields" in value:
                # Add the important fields to the params to guide the AI or filter results if supported
                # We use 'values' as some NetBox versions/plugins might support it, or it serves as documentation
                # But the user specifically asked to "include or replace the param fields"
                query["fields"] = value["fields"]
            break
    logger.info(f"get_resource called with endpoint: {resource}, params: {query}")
    return await netbox.get(resource, query)

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8080)

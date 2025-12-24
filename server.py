from fastmcp import FastMCP
import netbox
import validation
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
    - `netbox://graphql-schema`: Returns the GraphQL schema for the NetBox instance. Use this to understand the available types and fields for GraphQL queries.

    Tools:
    - `get_resource`: Fetches data from a specific NetBox endpoint. 
      - `endpoint`: The API path (e.g., 'dcim/devices'). Use the endpoints found in `netbox://object-types`.
      - `params`: A dictionary of query parameters for filtering (e.g., {'role': 'router', 'site': 'nyc'}).
    - `query_netbox_relationships`: Executes a GraphQL query against NetBox to fetch complex data, relationships, or aggregations.
      - `query`: The GraphQL query string.
    """,
    strict_input_validation=False
)

@mcp.resource("netbox://object-types")
def get_object_types() -> str:
    """Return the list of available NetBox object types and their endpoints."""
    logger.info("get_object_types called")
    return json.dumps(netbox.NETBOX_OBJECT_TYPES, indent=2)

@mcp.resource("netbox://graphql-schema")
async def get_graphql_schema() -> str:
    """Return the GraphQL schema for the NetBox instance."""
    query = """
    query {
      __schema {
        types {
          name
          kind
          description
          fields {
            name
            description
          }
        }
      }
    }
    """
    response = await netbox.graphql_get(query)
    if response and "data" in response:
        return json.dumps(response["data"], indent=2)
    return "Failed to fetch GraphQL schema"

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

    return await netbox.get(resource, query)

@mcp.tool()
async def query_netbox_relationships(
    query: Annotated[str, Field(description="The GraphQL query to execute. Use this for complex queries involving relationships, counts, or filtering across multiple models.")],
    action: Annotated[str, Field(description="Ignored parameter")] = None,
    sessionId: Annotated[str, Field(description="Ignored parameter")] = None,
    chatInput: Annotated[str, Field(description="Ignored parameter")] = None,
    metadata: Annotated[dict, Field(description="Ignored parameter")] = None,
    toolCallId: Annotated[str, Field(description="Ignored parameter")] = None,
) -> dict:
    """
    Execute a GraphQL query against NetBox. 
    
    Use this tool when the user asks questions about relationships between objects, counts, or aggregations.
    Examples:
    - "Who is the contact for site X?"
    - "How many devices are in rack Y?"
    - "List all interfaces for device Z."
    - "Show me all Cisco devices in New York."
    """
    logger.info(f"query_netbox_relationships called with query: {query}")
    return await netbox.graphql_get(query)

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8080)

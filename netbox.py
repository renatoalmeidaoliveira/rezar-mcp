import re
import os
import aiohttp
import asyncio
import logging
import validation
import re

from fastmcp.exceptions import ToolError


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

NETBOX_URL = os.environ.get("NETBOX_URL") or "http://netbox:8080/" 


async def get_field_choices(endpoint, field_name):
    api_token = os.environ.get("NETBOX_API_TOKEN")
    api_url = f"{NETBOX_URL}api/"
    url = f"{api_url}{endpoint}"
    params = {
        "limit": 0,
        "fields": field_name,}
    headers = {
        "accept": "application/json",
        "Authorization": f"Token {api_token}",
    }
    choices = set()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as r:
                response = await r.json()
                if r.status != 200:
                    raise LookupError(response)
                response = await r.json()
                for item in response["results"]:
                    if field_name in item and item[field_name] is not None:
                        value = item[field_name]
                        if isinstance(value, dict):
                            slug = value.get("slug")
                            if slug:
                                choices.add(slug)
                        else:
                            choices.add(value)
            while response["next"] is not None:
                async with session.get(
                    response["next"], headers=headers, params=params
                ) as r:
                    response = await r.json()
                    for item in response["results"]:
                        if field_name in item and item[field_name] is not None:
                            value = item[field_name]
                            if isinstance(value, dict):
                                slug = value.get("slug")
                                if slug:
                                    choices.add(slug)
                            else:
                                choices.add(value)
        logger.info(f"netbox.get_field_choices called with endpoint: {endpoint}, field_name: {field_name}, choices: {choices}")
        return list(choices)
    except Exception as e:
        logger.error(f"{e}")
        raise LookupError(f"Failed to get field choices from NetBox endpoint {endpoint} field {field_name} with reason {e}")
        return None


async def get(endpoint, params={}):
    slugfyed_fields = ['site', 'manufacturer', 'cluster_group', 'device_type',
                       'model','tenant',]
    model_assesors = ['site', 'manufacturer', 'cluster_group', 'device_type',
                       'device','tenant',  'contact', 'group', 'role', 'platform', 'location',
                       'rack', 'region', 'type', 'provider', 'circuit', 'virtual_circuit',
                       'power_panel', 'power_port', 'power_feed', 'module_type', 'module',
                       'interface', 'front_port', 'rear_port', 'console_port', 'console_server_port',
                       'cluster', 'virtual_device_context', 'vrf', 'vlan', 'prefix', 'aggregate',
                       'asn', 'asn_range', 'fhrp_group', 'ip_address', 'ip_range',
                       'service', 'device_role', 'rack_role', 
                       'circuit_type', 'virtual_circuit_type',]
    api_token = os.environ.get("NETBOX_API_TOKEN")
    api_url = f"{NETBOX_URL}api/"
    url = f"{api_url}{endpoint}"
    headers = {
        "accept": "application/json",
        "Authorization": f"Token {api_token}",
    }
    if "limit" not in params:
        params["limit"] = 1000
    if "fields" in params:
        params["fields"] = ",".join(params["fields"])
    output = {}
    not_validated_fields = {}
    for field in params:
        assessors = field.split("__")
        if len(assessors) >= 3:
            raise ToolError("Only one level of field lookup is supported, e.g., 'site__slug'")
        else:
            base_field = assessors[0]
            if base_field in slugfyed_fields:
                if assessors[1] == "slug":
                    params[base_field] = params.pop(field)[0]
                elif assessors[1] in model_assesors:
                    not_validated_fields[field] = params.pop(field)
    try:
        await validation.validate_path(await validation.get_schema(), f"/api/{endpoint}")
    except ValueError as e:
        raise ToolError(str(e))        
    try:
        await validation.validate_query_params(await validation.get_schema(), f"/api/{endpoint}", params)
    except ValueError as e:
        raise ToolError(str(e))
    for field in not_validated_fields:
        params[field] = not_validated_fields[field]
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as r:
                response = await r.json()
                if r.status == 400:
                    errors = []
                    choices_re = re.compile(r'Select a valid choice. .+? is not one of the available choices.')
                    for field in response:
                        for message in response[field]:
                            if choices_re.match(message):
                                field_choices = await get_field_choices(endpoint, field)
                                error_message = f"Invalid choice for field '{field}': Available choices are: {field_choices}"
                                errors.append(error_message)
                    raise ToolError("\n".join(errors))
                elif r.status != 200:
                    raise LookupError(response)
                response = await r.json()
                output["count"] = response["count"]
                output["results"] = []
                output["results"] = output["results"] + response["results"]
            while response["next"] is not None:
                async with session.get(
                    response["next"], headers=headers, params=params
                ) as r:
                    response = await r.json()
                    output["results"] = output["results"] + response["results"]
        return output
    except Exception as e:
        logger.error(f"{e}")
        raise LookupError(f"Failed to get data from NetBox endpoint {endpoint} with reason {e}")
        return None


async def graphql_get(query):
    api_token = os.environ.get("NETBOX_API_TOKEN")
    url = f"{NETBOX_URL}graphql/"
    headers = {
        "accept": "application/json",
        "Authorization": f"Token {api_token}",
        "Content-Type": "application/json",
    }
    payload = {"query": query}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as r:
                response = await r.json()
                if r.status != 200:
                    raise LookupError(response)
                return response
    except Exception as e:
        logger.error(f"{e}")
        raise LookupError(f"Failed to get data from NetBox graphql with reason {e}")
        return None


async def patch(endpoint, payload={}):
    api_token = os.environ.get("NETBOX_API_TOKEN")
    api_url = f"{NETBOX_URL}api/"
    url = f"{api_url}{endpoint}"
    headers = {
        "accept": "application/json",
        "Authorization": f"Token {api_token}",
    }
    output = {}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.patch(url, headers=headers, json=payload) as r:
                response = await r.json()
                if r.status != 200:
                    raise RuntimeError(
                        f"Failed to update Device with endpoint {endpoint} with reason {response}"
                    )
    except Exception as e:
        logger.error(f"{e.args}")


async def post(endpoint, payload={}):
    api_token = os.environ.get("NETBOX_API_TOKEN")
    api_url = f"{NETBOX_URL}api/"
    url = f"{api_url}{endpoint}"
    headers = {
        "accept": "application/json",
        "Authorization": f"Token {api_token}",
    }
    output = {}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as r:
                response = await r.json()
                if r.status != 201:
                    raise RuntimeError(
                        f"Failed to create with endpoint {endpoint} and payload {payload} with reason {response}"
                    )
        return response
    except Exception as e:
        logger.error(f"{e.args}")

async def delete(endpoint, model_id):
    api_token = os.environ.get("NETBOX_API_TOKEN")
    api_url = f"{NETBOX_URL}api/"
    url = f"{api_url}{endpoint}{model_id}/"
    headers = {
        "accept": "application/json",
        "Authorization": f"Token {api_token}",
    }        
    try:
        if model_id is None:
            raise Exception("model_id is None")
        if not isinstance(model_id, int):
            raise Exception("model_id is not an integer")
        async with aiohttp.ClientSession() as session:
            async with session.delete(url, headers=headers) as r:
                if r.status != 204:
                    response = await r.json()
                    raise RuntimeError(
                        f"Failed to delete with endpoint {endpoint} and id {model_id} with reason {response}"
                    )
    except Exception as e:
        logger.error(f"{e.args}")

NETBOX_OBJECT_TYPES = {
    "circuits.circuit": {
        "name": "Circuit",
        "endpoint": "circuits/circuits",
        "fields": ["url", "cid", "provider", "type", "status", "tenant", "description"]
    },
    "circuits.circuitgroup": {
        "name": "CircuitGroup",
        "endpoint": "circuits/circuit-groups",
        "fields": ["url", "name", "slug", "description"]
    },
    "circuits.circuitgroupassignment": {
        "name": "CircuitGroupAssignment",
        "endpoint": "circuits/circuit-group-assignments",
        "fields": ["url", "group", "member_type", "member_id", "priority"]
    },
    "circuits.circuittermination": {
        "name": "CircuitTermination",
        "endpoint": "circuits/circuit-terminations",
        "fields": ["url", "circuit", "term_side", "site", "provider_network", "port_speed", "upstream_speed"]
    },
    "circuits.circuittype": {
        "name": "CircuitType",
        "endpoint": "circuits/circuit-types",
        "fields": ["url", "name", "slug", "description"]
    },
    "circuits.provider": {
        "name": "Provider",
        "endpoint": "circuits/providers",
        "fields": ["url", "name", "slug", "asn", "account", "portal_url"]
    },
    "circuits.provideraccount": {
        "name": "ProviderAccount",
        "endpoint": "circuits/provider-accounts",
        "fields": ["url", "provider", "name", "account", "description"]
    },
    "circuits.providernetwork": {
        "name": "ProviderNetwork",
        "endpoint": "circuits/provider-networks",
        "fields": ["url", "provider", "name", "service_id", "description"]
    },
    "circuits.virtualcircuit": {
        "name": "VirtualCircuit",
        "endpoint": "circuits/virtual-circuits",
        "fields": ["url", "cid", "provider", "type", "status", "tenant", "description"]
    },
    "circuits.virtualcircuittermination": {
        "name": "VirtualCircuitTermination",
        "endpoint": "circuits/virtual-circuit-terminations",
        "fields": ["url", "virtual_circuit", "role", "interface"]
    },
    "circuits.virtualcircuittype": {
        "name": "VirtualCircuitType",
        "endpoint": "circuits/virtual-circuit-types",
        "fields": ["url", "name", "slug", "description"]
    },
    "core.datafile": {
        "name": "DataFile",
        "endpoint": "core/data-files",
        "fields": ["url", "source", "path", "last_updated", "size", "hash"]
    },
    "core.datasource": {
        "name": "DataSource",
        "endpoint": "core/data-sources",
        "fields": ["url", "name", "type", "source_url", "status", "description"]
    },
    "core.job": {
        "name": "Job",
        "endpoint": "core/jobs",
        "fields": ["url", "object_type", "name", "status", "created", "completed", "user"]
    },
    "core.objectchange": {
        "name": "ObjectChange",
        "endpoint": "core/object-changes",
        "fields": ["url", "time", "user", "user_name", "request_id", "action", "changed_object_type", "changed_object_id"]
    },
    "core.objecttype": {
        "name": "ObjectType",
        "endpoint": "extras/object-types",
        "fields": ["url", "app_label", "model"]
    },
    "dcim.cable": {
        "name": "Cable",
        "endpoint": "dcim/cables",
        "fields": ["url", "type", "status", "tenant", "label", "length", "length_unit"]
    },
    "dcim.cabletermination": {
        "name": "CableTermination",
        "endpoint": "dcim/cable-terminations",
        "fields": ["url", "cable", "cable_end", "termination_type", "termination_id"]
    },
    "dcim.consoleport": {
        "name": "ConsolePort",
        "endpoint": "dcim/console-ports",
        "fields": ["url", "device", "name", "label", "type", "speed", "description"]
    },
    "dcim.consoleporttemplate": {
        "name": "ConsolePortTemplate",
        "endpoint": "dcim/console-port-templates",
        "fields": ["url", "device_type", "name", "label", "type", "description"]
    },
    "dcim.consoleserverport": {
        "name": "ConsoleServerPort",
        "endpoint": "dcim/console-server-ports",
        "fields": ["url", "device", "name", "label", "type", "speed", "description"]
    },
    "dcim.consoleserverporttemplate": {
        "name": "ConsoleServerPortTemplate",
        "endpoint": "dcim/console-server-port-templates",
        "fields": ["url", "device_type", "name", "label", "type", "description"]
    },
    "dcim.device": {
        "name": "Device",
        "endpoint": "dcim/devices",
        "fields": ["url", "name", "device_type", "role", "tenant", "platform", "serial", "asset_tag", "site", "location", "rack", "position", "face", "status", "primary_ip"]
    },
    "dcim.devicebay": {
        "name": "DeviceBay",
        "endpoint": "dcim/device-bays",
        "fields": ["url", "device", "name", "label", "installed_device", "description"]
    },
    "dcim.devicebaytemplate": {
        "name": "DeviceBayTemplate",
        "endpoint": "dcim/device-bay-templates",
        "fields": ["url", "device_type", "name", "label", "description"]
    },
    "dcim.devicerole": {
        "name": "DeviceRole",
        "endpoint": "dcim/device-roles",
        "fields": ["url", "name", "slug", "color", "vm_role", "description"]
    },
    "dcim.devicetype": {
        "name": "DeviceType",
        "endpoint": "dcim/device-types",
        "fields": ["url", "manufacturer", "model", "slug", "part_number", "u_height", "is_full_depth", "subdevice_role"]
    },
    "dcim.frontport": {
        "name": "FrontPort",
        "endpoint": "dcim/front-ports",
        "fields": ["url", "device", "name", "label", "type", "rear_port", "rear_port_position", "description"]
    },
    "dcim.frontporttemplate": {
        "name": "FrontPortTemplate",
        "endpoint": "dcim/front-port-templates",
        "fields": ["url", "device_type", "name", "label", "type", "rear_port", "rear_port_position", "description"]
    },
    "dcim.interface": {
        "name": "Interface",
        "endpoint": "dcim/interfaces",
        "fields": ["url", "device", "name", "label", "type", "enabled", "mac_address", "mtu", "mode", "description"]
    },
    "dcim.interfacetemplate": {
        "name": "InterfaceTemplate",
        "endpoint": "dcim/interface-templates",
        "fields": ["url", "device_type", "name", "label", "type", "mgmt_only", "description"]
    },
    "dcim.inventoryitem": {
        "name": "InventoryItem",
        "endpoint": "dcim/inventory-items",
        "fields": ["url", "device", "parent", "name", "label", "role", "manufacturer", "part_id", "serial", "asset_tag", "description"]
    },
    "dcim.inventoryitemrole": {
        "name": "InventoryItemRole",
        "endpoint": "dcim/inventory-item-roles",
        "fields": ["url", "name", "slug", "color", "description"]
    },
    "dcim.inventoryitemtemplate": {
        "name": "InventoryItemTemplate",
        "endpoint": "dcim/inventory-item-templates",
        "fields": ["url", "device_type", "parent", "name", "label", "role", "manufacturer", "part_id", "description"]
    },
    "dcim.location": {
        "name": "Location",
        "endpoint": "dcim/locations",
        "fields": ["url", "name", "slug", "site", "parent", "status", "tenant", "description"]
    },
    "dcim.macaddress": {
        "name": "MACAddress",
        "endpoint": "dcim/mac-addresses",
        "fields": ["url", "mac_address", "assigned_object_type", "assigned_object_id", "description"]
    },
    "dcim.manufacturer": {
        "name": "Manufacturer",
        "endpoint": "dcim/manufacturers",
        "fields": ["url", "name", "slug", "description"]
    },
    "dcim.module": {
        "name": "Module",
        "endpoint": "dcim/modules",
        "fields": ["url", "device", "module_bay", "module_type", "status", "serial", "asset_tag", "description"]
    },
    "dcim.modulebay": {
        "name": "ModuleBay",
        "endpoint": "dcim/module-bays",
        "fields": ["url", "device", "name", "label", "position", "installed_module", "description"]
    },
    "dcim.modulebaytemplate": {
        "name": "ModuleBayTemplate",
        "endpoint": "dcim/module-bay-templates",
        "fields": ["url", "device_type", "name", "label", "position", "description"]
    },
    "dcim.moduletype": {
        "name": "ModuleType",
        "endpoint": "dcim/module-types",
        "fields": ["url", "manufacturer", "model", "part_number", "weight", "weight_unit", "description"]
    },
    "dcim.moduletypeprofile": {
        "name": "ModuleTypeProfile",
        "endpoint": "dcim/module-type-profiles",
        "fields": ["url", "name", "module_type", "description"]
    },
    "dcim.platform": {
        "name": "Platform",
        "endpoint": "dcim/platforms",
        "fields": ["url", "name", "slug", "manufacturer", "napalm_driver", "description"]
    },
    "dcim.powerfeed": {
        "name": "PowerFeed",
        "endpoint": "dcim/power-feeds",
        "fields": ["url", "power_panel", "rack", "name", "status", "type", "supply", "phase", "voltage", "amperage", "max_utilization", "description"]
    },
    "dcim.poweroutlet": {
        "name": "PowerOutlet",
        "endpoint": "dcim/power-outlets",
        "fields": ["url", "device", "name", "label", "type", "power_port", "feed_leg", "description"]
    },
    "dcim.poweroutlettemplate": {
        "name": "PowerOutletTemplate",
        "endpoint": "dcim/power-outlet-templates",
        "fields": ["url", "device_type", "name", "label", "type", "power_port", "feed_leg", "description"]
    },
    "dcim.powerpanel": {
        "name": "PowerPanel",
        "endpoint": "dcim/power-panels",
        "fields": ["url", "site", "location", "name", "description"]
    },
    "dcim.powerport": {
        "name": "PowerPort",
        "endpoint": "dcim/power-ports",
        "fields": ["url", "device", "name", "label", "type", "maximum_draw", "allocated_draw", "description"]
    },
    "dcim.powerporttemplate": {
        "name": "PowerPortTemplate",
        "endpoint": "dcim/power-port-templates",
        "fields": ["url", "device_type", "name", "label", "type", "maximum_draw", "allocated_draw", "description"]
    },
    "dcim.rack": {
        "name": "Rack",
        "endpoint": "dcim/racks",
        "fields": ["url", "name", "facility_id", "site", "location", "tenant", "status", "role", "serial", "asset_tag", "type", "width", "u_height", "desc_units", "outer_width", "outer_depth", "outer_unit", "description"]
    },
    "dcim.rackreservation": {
        "name": "RackReservation",
        "endpoint": "dcim/rack-reservations",
        "fields": ["url", "rack", "units", "user", "tenant", "description"]
    },
    "dcim.rackrole": {
        "name": "RackRole",
        "endpoint": "dcim/rack-roles",
        "fields": ["url", "name", "slug", "color", "description"]
    },
    "dcim.racktype": {
        "name": "RackType",
        "endpoint": "dcim/rack-types",
        "fields": ["url", "manufacturer", "model", "slug", "width", "u_height", "outer_width", "outer_depth", "outer_unit", "weight", "weight_unit", "max_weight", "max_weight_unit", "description"]
    },
    "dcim.rearport": {
        "name": "RearPort",
        "endpoint": "dcim/rear-ports",
        "fields": ["url", "device", "name", "label", "type", "positions", "description"]
    },
    "dcim.rearporttemplate": {
        "name": "RearPortTemplate",
        "endpoint": "dcim/rear-port-templates",
        "fields": ["url", "device_type", "name", "label", "type", "positions", "description"]
    },
    "dcim.region": {
        "name": "Region",
        "endpoint": "dcim/regions",
        "fields": ["url", "name", "slug", "parent", "description"]
    },
    "dcim.site": {
        "name": "Site",
        "endpoint": "dcim/sites",
        "fields": ["url", "name", "slug", "status", "region", "group", "tenant", "id", "facility","description"]
    },
    "dcim.sitegroup": {
        "name": "SiteGroup",
        "endpoint": "dcim/site-groups",
        "fields": ["url", "name", "slug", "parent", "description"]
    },
    "dcim.virtualchassis": {
        "name": "VirtualChassis",
        "endpoint": "dcim/virtual-chassis",
        "fields": ["url", "name", "domain", "master", "description"]
    },
    "dcim.virtualdevicecontext": {
        "name": "VirtualDeviceContext",
        "endpoint": "dcim/virtual-device-contexts",
        "fields": ["url", "name", "device", "status", "tenant", "primary_ip", "description"]
    },
    "extras.bookmark": {
        "name": "Bookmark",
        "endpoint": "extras/bookmarks",
        "fields": ["url", "object_type", "object_id", "user", "created"]
    },
    "extras.configcontext": {
        "name": "ConfigContext",
        "endpoint": "extras/config-contexts",
        "fields": ["url", "name", "weight", "description", "is_active"]
    },
    "extras.configtemplate": {
        "name": "ConfigTemplate",
        "endpoint": "extras/config-templates",
        "fields": ["url", "name", "description", "environment_params"]
    },
    "extras.customfield": {
        "name": "CustomField",
        "endpoint": "extras/custom-fields",
        "fields": ["url", "name", "label", "type", "required", "filter_logic", "default", "weight", "description"]
    },
    "extras.customfieldchoiceset": {
        "name": "CustomFieldChoiceSet",
        "endpoint": "extras/custom-field-choice-sets",
        "fields": ["url", "name", "description", "base_choices", "extra_choices"]
    },
    "extras.customlink": {
        "name": "CustomLink",
        "endpoint": "extras/custom-links",
        "fields": ["url", "name", "content_type", "link_text", "link_url", "weight", "group_name", "button_class", "new_window"]
    },
    "extras.eventrule": {
        "name": "EventRule",
        "endpoint": "extras/event-rules",
        "fields": ["url", "name", "type_create", "type_update", "type_delete", "enabled", "conditions", "action_type", "action_object_type", "action_object_id", "description"]
    },
    "extras.exporttemplate": {
        "name": "ExportTemplate",
        "endpoint": "extras/export-templates",
        "fields": ["url", "name", "content_type", "description", "template_code", "mime_type", "file_extension"]
    },
    "extras.imageattachment": {
        "name": "ImageAttachment",
        "endpoint": "extras/image-attachments",
        "fields": ["url", "content_type", "object_id", "name", "image", "image_height", "image_width", "created"]
    },
    "extras.journalentry": {
        "name": "JournalEntry",
        "endpoint": "extras/journal-entries",
        "fields": ["url", "assigned_object_type", "assigned_object_id", "created_by", "kind", "comments"]
    },
    "extras.notification": {
        "name": "Notification",
        "endpoint": "extras/notifications",
        "fields": ["url", "created", "read", "user", "event_rule", "object_type", "object_id"]
    },
    "extras.notificationgroup": {
        "name": "NotificationGroup",
        "endpoint": "extras/notification-groups",
        "fields": ["url", "name", "description"]
    },
    "extras.savedfilter": {
        "name": "SavedFilter",
        "endpoint": "extras/saved-filters",
        "fields": ["url", "name", "slug", "content_type", "user", "weight", "enabled", "shared", "description"]
    },
    "extras.script": {
        "name": "Script",
        "endpoint": "extras/scripts",
        "fields": ["url", "name", "module", "result", "created"]
    },
    "extras.subscription": {
        "name": "Subscription",
        "endpoint": "extras/subscriptions",
        "fields": ["url", "user", "object_type", "object_id"]
    },
    "extras.tableconfig": {
        "name": "TableConfig",
        "endpoint": "extras/table-configs",
        "fields": ["url", "user", "content_type", "columns"]
    },
    "extras.tag": {
        "name": "Tag",
        "endpoint": "extras/tags",
        "fields": ["url", "name", "slug", "color", "description"]
    },
    "extras.taggeditem": {
        "name": "TaggedItem",
        "endpoint": "extras/tagged-objects",
        "fields": ["url", "object_type", "object_id", "tag"]
    },
    "extras.webhook": {
        "name": "Webhook",
        "endpoint": "extras/webhooks",
        "fields": ["url", "name", "type_create", "type_update", "type_delete", "payload_url", "enabled", "http_method", "http_content_type", "ssl_verification"]
    },
    "ipam.aggregate": {
        "name": "Aggregate",
        "endpoint": "ipam/aggregates",
        "fields": ["url", "prefix", "rir", "tenant", "date_added", "description"]
    },
    "ipam.asn": {
        "name": "ASN",
        "endpoint": "ipam/asns",
        "fields": ["url", "asn", "rir", "tenant", "description"]
    },
    "ipam.asnrange": {
        "name": "ASNRange",
        "endpoint": "ipam/asn-ranges",
        "fields": ["url", "name", "slug", "rir", "start", "end", "tenant", "description"]
    },
    "ipam.fhrpgroup": {
        "name": "FHRPGroup",
        "endpoint": "ipam/fhrp-groups",
        "fields": ["url", "group_id", "protocol", "auth_type", "auth_key", "description"]
    },
    "ipam.fhrpgroupassignment": {
        "name": "FHRPGroupAssignment",
        "endpoint": "ipam/fhrp-group-assignments",
        "fields": ["url", "group", "interface_type", "interface_id", "priority"]
    },
    "ipam.ipaddress": {
        "name": "IPAddress",
        "endpoint": "ipam/ip-addresses",
        "fields": ["url", "address", "vrf", "tenant", "status", "role", "assigned_object_type", "assigned_object_id", "nat_inside", "dns_name", "description"]
    },
    "ipam.iprange": {
        "name": "IPRange",
        "endpoint": "ipam/ip-ranges",
        "fields": ["url", "start_address", "end_address", "vrf", "tenant", "status", "role", "description"]
    },
    "ipam.prefix": {
        "name": "Prefix",
        "endpoint": "ipam/prefixes",
        "fields": ["url", "prefix", "site", "vrf", "tenant", "vlan", "status", "role", "is_pool", "description"]
    },
    "ipam.rir": {
        "name": "RIR",
        "endpoint": "ipam/rirs",
        "fields": ["url", "name", "slug", "is_private", "description"]
    },
    "ipam.role": {
        "name": "Role",
        "endpoint": "ipam/roles",
        "fields": ["url", "name", "slug", "weight", "description"]
    },
    "ipam.routetarget": {
        "name": "RouteTarget",
        "endpoint": "ipam/route-targets",
        "fields": ["url", "name", "tenant", "description"]
    },
    "ipam.service": {
        "name": "Service",
        "endpoint": "ipam/services",
        "fields": ["url", "device", "virtual_machine", "name", "protocol", "ports", "ipaddresses", "description"]
    },
    "ipam.servicetemplate": {
        "name": "ServiceTemplate",
        "endpoint": "ipam/service-templates",
        "fields": ["url", "name", "protocol", "ports", "description"]
    },
    "ipam.vlan": {
        "name": "VLAN",
        "endpoint": "ipam/vlans",
        "fields": ["url", "site", "group", "vid", "name", "tenant", "status", "role", "description"]
    },
    "ipam.vlangroup": {
        "name": "VLANGroup",
        "endpoint": "ipam/vlan-groups",
        "fields": ["url", "name", "slug", "scope_type", "scope_id", "min_vid", "max_vid", "description"]
    },
    "ipam.vlantranslationpolicy": {
        "name": "VLANTranslationPolicy",
        "endpoint": "ipam/vlan-translation-policies",
        "fields": ["url", "name", "description"]
    },
    "ipam.vlantranslationrule": {
        "name": "VLANTranslationRule",
        "endpoint": "ipam/vlan-translation-rules",
        "fields": ["url", "policy", "local_vid", "remote_vid", "description"]
    },
    "ipam.vrf": {
        "name": "VRF",
        "endpoint": "ipam/vrfs",
        "fields": ["url", "name", "rd", "tenant", "enforce_unique", "description"]
    },
    "tenancy.contact": {
        "name": "Contact",
        "endpoint": "tenancy/contacts",
        "fields": ["url", "group", "name", "title", "phone", "email", "address", "link", "description"]
    },
    "tenancy.contactassignment": {
        "name": "ContactAssignment",
        "endpoint": "tenancy/contact-assignments",
        "fields": ["url", "content_type", "object_id", "contact", "role", "priority"]
    },
    "tenancy.contactgroup": {
        "name": "ContactGroup",
        "endpoint": "tenancy/contact-groups",
        "fields": ["url", "name", "slug", "parent", "description"]
    },
    "tenancy.contactrole": {
        "name": "ContactRole",
        "endpoint": "tenancy/contact-roles",
        "fields": ["url", "name", "slug", "description"]
    },
    "tenancy.tenant": {
        "name": "Tenant",
        "endpoint": "tenancy/tenants",
        "fields": ["url", "name", "slug", "group", "description"]
    },
    "tenancy.tenantgroup": {
        "name": "TenantGroup",
        "endpoint": "tenancy/tenant-groups",
        "fields": ["url", "name", "slug", "parent", "description"]
    },
    "users.group": {
        "name": "Group",
        "endpoint": "users/groups",
        "fields": ["url", "name", "permissions"]
    },
    "users.objectpermission": {
        "name": "ObjectPermission",
        "endpoint": "users/permissions",
        "fields": ["url", "name", "description", "enabled", "object_types", "groups", "users", "actions", "constraints"]
    },
    "users.token": {
        "name": "Token",
        "endpoint": "users/tokens",
        "fields": ["url", "user", "created", "expires", "key", "write_enabled", "description"]
    },
    "users.user": {
        "name": "User",
        "endpoint": "users/users",
        "fields": ["url", "username", "first_name", "last_name", "email", "is_staff", "is_active", "date_joined", "groups"]
    },
    "virtualization.cluster": {
        "name": "Cluster",
        "endpoint": "virtualization/clusters",
        "fields": ["url", "name", "type", "group", "status", "tenant", "site", "description"]
    },
    "virtualization.clustergroup": {
        "name": "ClusterGroup",
        "endpoint": "virtualization/cluster-groups",
        "fields": ["url", "name", "slug", "description"]
    },
    "virtualization.clustertype": {
        "name": "ClusterType",
        "endpoint": "virtualization/cluster-types",
        "fields": ["url", "name", "slug", "description"]
    },
    "virtualization.virtualdisk": {
        "name": "VirtualDisk",
        "endpoint": "virtualization/virtual-disks",
        "fields": ["url", "virtual_machine", "name", "size", "description"]
    },
    "virtualization.virtualmachine": {
        "name": "VirtualMachine",
        "endpoint": "virtualization/virtual-machines",
        "fields": ["url", "name", "status", "site", "cluster", "device", "role", "tenant", "platform", "primary_ip", "vcpus", "memory", "disk", "description"]
    },
    "virtualization.vminterface": {
        "name": "VMInterface",
        "endpoint": "virtualization/interfaces",
        "fields": ["url", "virtual_machine", "name", "enabled", "mac_address", "mtu", "mode", "description"]
    },
    "vpn.ikepolicy": {
        "name": "IKEPolicy",
        "endpoint": "vpn/ike-policies",
        "fields": ["url", "name", "version", "mode", "proposals", "preshared_key", "description"]
    },
    "vpn.ikeproposal": {
        "name": "IKEProposal",
        "endpoint": "vpn/ike-proposals",
        "fields": ["url", "name", "authentication_method", "encryption_algorithm", "authentication_algorithm", "group", "sa_lifetime", "description"]
    },
    "vpn.ipsecpolicy": {
        "name": "IPSecPolicy",
        "endpoint": "vpn/ipsec-policies",
        "fields": ["url", "name", "proposals", "pfs_group", "description"]
    },
    "vpn.ipsecprofile": {
        "name": "IPSecProfile",
        "endpoint": "vpn/ipsec-profiles",
        "fields": ["url", "name", "mode", "ike_policy", "ipsec_policy", "description"]
    },
    "vpn.ipsecproposal": {
        "name": "IPSecProposal",
        "endpoint": "vpn/ipsec-proposals",
        "fields": ["url", "name", "encryption_algorithm", "authentication_algorithm", "sa_lifetime_seconds", "sa_lifetime_data", "description"]
    },
    "vpn.l2vpn": {
        "name": "L2VPN",
        "endpoint": "vpn/l2vpns",
        "fields": ["url", "name", "slug", "type", "identifier", "import_targets", "export_targets", "tenant", "description"]
    },
    "vpn.l2vpntermination": {
        "name": "L2VPNTermination",
        "endpoint": "vpn/l2vpn-terminations",
        "fields": ["url", "l2vpn", "assigned_object_type", "assigned_object_id"]
    },
    "vpn.tunnel": {
        "name": "Tunnel",
        "endpoint": "vpn/tunnels",
        "fields": ["url", "name", "status", "group", "encapsulation", "ipsec_profile", "tenant", "tunnel_id", "description"]
    },
    "vpn.tunnelgroup": {
        "name": "TunnelGroup",
        "endpoint": "vpn/tunnel-groups",
        "fields": ["url", "name", "slug", "description"]
    },
    "vpn.tunneltermination": {
        "name": "TunnelTermination",
        "endpoint": "vpn/tunnel-terminations",
        "fields": ["url", "tunnel", "role", "termination_type", "termination_id", "outside_ip"]
    },
    "wireless.wirelesslan": {
        "name": "WirelessLAN",
        "endpoint": "wireless/wireless-lans",
        "fields": ["url", "ssid", "group", "status", "vlan", "tenant", "auth_type", "auth_cipher", "auth_psk", "description"]
    },
    "wireless.wirelesslangroup": {
        "name": "WirelessLANGroup",
        "endpoint": "wireless/wireless-lan-groups",
        "fields": ["url", "name", "slug", "parent", "description"]
    },
    "wireless.wirelesslink": {
        "name": "WirelessLink",
        "endpoint": "wireless/wireless-links",
        "fields": ["url", "interface_a", "interface_b", "ssid", "status", "tenant", "auth_type", "auth_cipher", "auth_psk", "description"]
    },
}

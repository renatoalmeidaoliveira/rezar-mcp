import asyncio
import unittest

import netbox

class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_path(self):
        invalid_path = "/api/invalid/endpoint/"
        with self.assertRaises(ValueError) as context:
            await netbox.get(invalid_path)
            self.assertIn("does not exist", str(context.exception))

    async def test_valid_path(self):
        valid_path = "dcim/devices/"
        try:
            await netbox.get(valid_path)
        except ValueError:
            self.fail(f"validate_path raised ValueError unexpectedly for path: {valid_path}")
       
    async def test_invalid_query_params(self):
        valid_path = "dcim/devices/"
        invalid_params = {"invalid_param": "value"}
        with self.assertRaises(ValueError) as context:
            await netbox.get(valid_path, params=invalid_params)
            self.assertIn("Invalid query parameters", str(context.exception))
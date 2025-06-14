"""FastMCP integration for external tool support"""

import logging
from rich.console import Console
from rich.table import Table

logger = logging.getLogger(__name__)
console = Console()

# FastMCP imports (optional advanced feature)
try:
    # Try different possible imports for FastMCP
    try:
        from fastmcp import FastMCPClient
    except ImportError:
        from fastmcp.client import FastMCPClient
    
    try:
        from fastmcp.server import MCPServer
    except ImportError:
        MCPServer = None
        
    MCP_AVAILABLE = True
    logger.info("FastMCP available for MCP server integration")
except ImportError:
    MCP_AVAILABLE = False
    logger.info("FastMCP not available - this is optional for advanced MCP server integration")


class FastMCPIntegration:
    def __init__(self):
        self.clients = {}
        self.available_tools = {}
        self.connected_servers = {}
        
    async def connect_server(self, server_name, server_config):
        """Connect to an MCP server using FastMCP"""
        if not MCP_AVAILABLE:
            console.print("❌ [red]FastMCP not available[/red]")
            return False
            
        try:
            if server_config['type'] == 'stdio':
                client = FastMCPClient()
                await client.connect_stdio(
                    command=server_config['command'],
                    args=server_config.get('args', []),
                    env=server_config.get('env', {})
                )
            elif server_config['type'] == 'websocket':
                client = FastMCPClient()
                await client.connect_websocket(server_config['url'])
            else:
                console.print(f"❌ [red]Unsupported server type: {server_config['type']}[/red]")
                return False
            
            self.clients[server_name] = client
            self.connected_servers[server_name] = server_config
            
            # Get available tools from this server
            tools = await client.list_tools()
            for tool in tools:
                tool_key = f"{server_name}.{tool.name}"
                self.available_tools[tool_key] = {
                    'server': server_name,
                    'tool': tool,
                    'client': client
                }
            
            console.print(f"✅ [green]Connected to {server_name} ({len(tools)} tools available)[/green]")
            return True
            
        except Exception as e:
            console.print(f"❌ [red]Failed to connect to {server_name}: {e}[/red]")
            return False
    
    async def call_tool(self, tool_key, **kwargs):
        """Call an MCP tool"""
        if tool_key not in self.available_tools:
            return f"Tool {tool_key} not found"
        
        tool_info = self.available_tools[tool_key]
        client = tool_info['client']
        tool = tool_info['tool']
        
        try:
            result = await client.call_tool(tool.name, kwargs)
            return result
        except Exception as e:
            return f"Error calling {tool_key}: {e}"
    
    def get_available_tools(self):
        """Get list of all available MCP tools"""
        return list(self.available_tools.keys())
    
    def get_tool_info(self, tool_key):
        """Get detailed info about a specific tool"""
        if tool_key in self.available_tools:
            tool_info = self.available_tools[tool_key]
            return {
                'name': tool_info['tool'].name,
                'description': tool_info['tool'].description,
                'server': tool_info['server'],
                'parameters': tool_info['tool'].inputSchema
            }
        return None
    
    async def disconnect_all(self):
        """Disconnect from all MCP servers"""
        for client in self.clients.values():
            try:
                await client.disconnect()
            except:
                pass
        self.clients.clear()
        self.available_tools.clear()
        self.connected_servers.clear()
"""MCP Apps resource plus ChatGPT compatibility metadata, without device GPS access."""
from pathlib import Path
from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from mcp.types import ReadResourceRequest, ReadResourceResult
from .presentation import UI_URI

UI_META={
    'ui':{'prefersBorder':True,'csp':{'connectDomains':[],'resourceDomains':['https://tile.openstreetmap.org']}},
    'openai/widgetPrefersBorder':True,
    'openai/widgetDescription':'Bản đồ chung và tối đa 10 quán gần đến xa, menu Hàn–Việt, giá, review và dữ liệu thiếu rõ ràng.',
    'openai/widgetCSP':{'connect_domains':[],'resource_domains':['https://tile.openstreetmap.org']},
}
TOOL_META={'ui':{'resourceUri':UI_URI},'openai/outputTemplate':UI_URI}


def html():
    root=Path(__file__).parent/'static'
    return (root/'restaurant-widget.html').read_text().replace('__STYLE__',(root/'restaurant-widget.css').read_text()).replace('__SCRIPT__',(root/'restaurant-widget.js').read_text())


class TouristMCP(FastMCP):
    def _setup_read_resource_handler(self):
        # FastMCP 2.14 converts resource contents but drops their _meta.
        # Wrap the SDK boundary after normal resource/middleware validation.
        super()._setup_read_resource_handler()
        original=self._mcp_server.request_handlers[ReadResourceRequest]
        async def handler(request):
            result=await original(request)
            if str(request.params.uri)==UI_URI and isinstance(result.root,ReadResourceResult):
                for content in result.root.contents:
                    content.meta=UI_META
            return result
        self._mcp_server.request_handlers[ReadResourceRequest]=handler


def tool_result(data):
    return ToolResult(content=data['markdown'],structured_content=data)

"""MCP Apps resource plus ChatGPT compatibility metadata, without device GPS access."""
from pathlib import Path
from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from mcp.server.lowlevel.helper_types import ReadResourceContents
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
    async def _read_resource(self,context):
        contents=await super()._read_resource(context)
        if str(context.message.uri)==UI_URI:
            # FastMCP 2.x does not forward resource metadata to resources/read contents.
            return [ReadResourceContents(content=c.content,mime_type=c.mime_type,meta=UI_META) for c in contents]
        return contents


def tool_result(data):
    return ToolResult(content=data['markdown'],structured_content=data)

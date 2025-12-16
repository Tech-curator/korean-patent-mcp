"""
Smithery Config Middleware
Smithery에서 전달되는 session configuration을 파싱하는 미들웨어
"""
from smithery.utils.config import parse_config_from_asgi_scope


class SmitheryConfigMiddleware:
    """
    Middleware to extract Smithery configuration from ASGI scope.
    
    This middleware parses configuration passed via query parameters
    and stores it in the request scope for per-request access.
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope.get('type') == 'http':
            try:
                scope['smithery_config'] = parse_config_from_asgi_scope(scope)
            except Exception as e:
                print(f"SmitheryConfigMiddleware: Error parsing config: {e}")
                scope['smithery_config'] = {}
        await self.app(scope, receive, send)

"""
Smithery Config Middleware
Smithery에서 전달되는 session configuration을 파싱하는 미들웨어
"""
from contextvars import ContextVar
from smithery.utils.config import parse_config_from_asgi_scope

# ContextVar를 정의하여 요청 간에 설정을 안전하게 전달
smithery_context: ContextVar[dict] = ContextVar("smithery_config", default={})


class SmitheryConfigMiddleware:
    """
    Middleware to extract Smithery configuration from ASGI scope.
    
    This middleware parses configuration passed via query parameters
    and stores it in a ContextVar for per-request access by tools.
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        config = {}
        if scope.get('type') == 'http':
            try:
                # Smithery 설정 파싱
                config = parse_config_from_asgi_scope(scope)
            except Exception as e:
                print(f"SmitheryConfigMiddleware: Error parsing config: {e}")
        
        # 파싱한 설정을 ContextVar에 저장 (도구에서 smithery_context.get()으로 꺼내 씀)
        token = smithery_context.set(config)
        try:
            await self.app(scope, receive, send)
        finally:
            # 요청이 끝나면 초기화
            smithery_context.reset(token)

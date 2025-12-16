"""
Korean Patent MCP Server
한국 특허정보 검색서비스를 위한 MCP 서버
"""
import json
from typing import Optional
from enum import Enum
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ConfigDict

from .kipris_api import KiprisAPIClient, KiprisConfig


# =========================================================================
# Response Format
# =========================================================================

class ResponseFormat(str, Enum):
    """응답 형식"""
    MARKDOWN = "markdown"
    JSON = "json"


# =========================================================================
# Input Models (Pydantic)
# =========================================================================

class SearchPatentsInput(BaseModel):
    """출원인 검색 입력 모델"""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    applicant_name: str = Field(
        ...,
        description="출원인명 (예: '삼성전자', '충북대학교 산학협력단')",
        min_length=1,
        max_length=200
    )
    page: int = Field(
        default=1,
        description="페이지 번호 (1부터 시작)",
        ge=1
    )
    page_size: int = Field(
        default=20,
        description="페이지당 결과 수 (최대 100)",
        ge=1,
        le=100
    )
    status: Optional[str] = Field(
        default=None,
        description="상태 필터: 'A'(공개), 'R'(등록), 'J'(거절), None(전체)"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="응답 형식: 'markdown' 또는 'json'"
    )


class GetPatentDetailInput(BaseModel):
    """특허 상세 정보 조회 입력 모델"""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    application_number: str = Field(
        ...,
        description="출원번호 (예: '1020200123456' 또는 '10-2020-0123456')",
        min_length=1
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="응답 형식: 'markdown' 또는 'json'"
    )


class GetCitingPatentsInput(BaseModel):
    """인용 특허 조회 입력 모델"""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    application_number: str = Field(
        ...,
        description="기준 특허의 출원번호 (이 특허를 인용한 후행 특허들을 검색)",
        min_length=1
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="응답 형식: 'markdown' 또는 'json'"
    )


# =========================================================================
# Formatting Helpers
# =========================================================================

def format_patent_markdown(patent: dict, detailed: bool = False) -> str:
    """특허 정보를 마크다운으로 포맷팅"""
    lines = []
    lines.append(f"### {patent.get('title', '제목 없음')}")
    lines.append("")
    lines.append(f"- **출원번호**: {patent.get('application_number', '-')}")
    lines.append(f"- **출원일**: {patent.get('application_date', '-')}")
    lines.append(f"- **출원인**: {patent.get('applicant', '-')}")
    lines.append(f"- **등록상태**: {patent.get('registration_status', '-')}")
    
    if patent.get('opening_number'):
        lines.append(f"- **공개번호**: {patent.get('opening_number')} ({patent.get('opening_date', '-')})")
    
    if patent.get('registration_number'):
        lines.append(f"- **등록번호**: {patent.get('registration_number')} ({patent.get('registration_date', '-')})")
    
    if detailed:
        if patent.get('ipc_number'):
            lines.append(f"- **IPC 분류**: {patent.get('ipc_number')}")
        if patent.get('abstract'):
            lines.append("")
            lines.append("**초록**:")
            lines.append(f"> {patent.get('abstract')[:500]}...")
    
    return "\n".join(lines)


def format_search_result_markdown(result: dict) -> str:
    """검색 결과를 마크다운으로 포맷팅"""
    lines = []
    lines.append(f"## 검색 결과")
    lines.append("")
    lines.append(f"총 **{result['total_count']:,}**건 중 {len(result['patents'])}건 표시 (페이지 {result['page']})")
    lines.append("")
    
    if not result['patents']:
        lines.append("검색 결과가 없습니다.")
        return "\n".join(lines)
    
    for i, patent in enumerate(result['patents'], 1):
        lines.append(f"---")
        lines.append(f"**[{i}]** {patent.get('title', '제목 없음')}")
        lines.append(f"- 출원번호: `{patent.get('application_number', '-')}`")
        lines.append(f"- 출원인: {patent.get('applicant', '-')}")
        lines.append(f"- 상태: {patent.get('registration_status', '-')}")
        lines.append("")
    
    if result.get('has_more'):
        lines.append(f"---")
        lines.append(f"📄 다음 페이지: `page={result['next_page']}`")
    
    return "\n".join(lines)


def format_citing_patents_markdown(citations: list, base_app_num: str) -> str:
    """인용 특허 목록을 마크다운으로 포맷팅"""
    lines = []
    lines.append(f"## 인용 특허 조회 결과")
    lines.append("")
    lines.append(f"기준 특허 `{base_app_num}`를 인용한 후행 특허: **{len(citations)}**건")
    lines.append("")
    
    if not citations:
        lines.append("이 특허를 인용한 후행 특허가 없습니다.")
        return "\n".join(lines)
    
    for i, cite in enumerate(citations, 1):
        lines.append(f"---")
        lines.append(f"**[{i}]** 출원번호: `{cite.get('citing_application_number', '-')}`")
        lines.append(f"- 상태: {cite.get('status_name', '-')} ({cite.get('status_code', '-')})")
        lines.append(f"- 인용유형: {cite.get('citation_type_name', '-')}")
        lines.append("")
    
    return "\n".join(lines)


# =========================================================================
# MCP Server Setup
# =========================================================================

@asynccontextmanager
async def app_lifespan():
    """서버 생명주기 관리 - API 클라이언트 초기화/정리"""
    try:
        config = KiprisConfig.from_env()
        client = KiprisAPIClient(config)
        yield {"kipris_client": client}
    except ValueError as e:
        yield {"kipris_client": None, "init_error": str(e)}
    finally:
        if 'client' in locals():
            await client.close()


# MCP 서버 초기화
mcp = FastMCP(
    "korean_patent_mcp",
    lifespan=app_lifespan
)


# =========================================================================
# Tool Definitions
# =========================================================================

@mcp.tool(
    name="kipris_search_patents",
    annotations={
        "title": "한국 특허 검색 (출원인)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def kipris_search_patents(params: SearchPatentsInput) -> str:
    """출원인명으로 한국 특허를 검색합니다.
    
    KIPRIS(한국특허정보검색서비스) API를 사용하여 특정 출원인(회사, 기관, 개인)의 
    특허를 검색합니다. 페이지네이션을 지원하며, 상태별 필터링이 가능합니다.
    
    Args:
        params (SearchPatentsInput): 검색 파라미터
            - applicant_name: 출원인명 (필수)
            - page: 페이지 번호 (기본값: 1)
            - page_size: 페이지당 결과 수 (기본값: 20, 최대: 100)
            - status: 상태 필터 ('A': 공개, 'R': 등록, 'J': 거절)
            - response_format: 응답 형식 ('markdown' 또는 'json')
    
    Returns:
        str: 검색 결과 (마크다운 또는 JSON 형식)
    
    Example:
        - 삼성전자의 등록 특허 검색: applicant_name="삼성전자", status="R"
        - 대학 산학협력단 특허: applicant_name="서울대학교 산학협력단"
    """
    from mcp.server.fastmcp import Context
    ctx = Context.current()
    
    client = ctx.request_context.lifespan_state.get("kipris_client")
    if client is None:
        error = ctx.request_context.lifespan_state.get("init_error", "API 클라이언트 초기화 실패")
        return f"❌ 오류: {error}"
    
    try:
        result = await client.search_patents_by_applicant(
            applicant_name=params.applicant_name,
            page=params.page,
            page_size=params.page_size,
            status=params.status or ""
        )
        
        if params.response_format == ResponseFormat.JSON:
            return json.dumps(result, ensure_ascii=False, indent=2)
        else:
            return format_search_result_markdown(result)
            
    except Exception as e:
        return f"❌ 검색 오류: {str(e)}"


@mcp.tool(
    name="kipris_get_patent_detail",
    annotations={
        "title": "한국 특허 상세 정보",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def kipris_get_patent_detail(params: GetPatentDetailInput) -> str:
    """출원번호로 특허의 상세 정보를 조회합니다.
    
    특정 특허의 출원번호를 사용하여 상세 정보(제목, 출원인, 초록, IPC 분류 등)를 
    조회합니다.
    
    Args:
        params (GetPatentDetailInput): 조회 파라미터
            - application_number: 출원번호 (필수, 예: '1020200123456')
            - response_format: 응답 형식 ('markdown' 또는 'json')
    
    Returns:
        str: 특허 상세 정보 (마크다운 또는 JSON 형식)
    
    Example:
        - application_number="1020200123456"
        - application_number="10-2020-0123456" (하이픈 포함도 가능)
    """
    from mcp.server.fastmcp import Context
    ctx = Context.current()
    
    client = ctx.request_context.lifespan_state.get("kipris_client")
    if client is None:
        error = ctx.request_context.lifespan_state.get("init_error", "API 클라이언트 초기화 실패")
        return f"❌ 오류: {error}"
    
    app_num = params.application_number.replace("-", "")
    
    try:
        result = await client.get_patent_detail(app_num)
        
        if result is None:
            return f"❌ 출원번호 `{params.application_number}`에 해당하는 특허를 찾을 수 없습니다."
        
        if params.response_format == ResponseFormat.JSON:
            return json.dumps(result, ensure_ascii=False, indent=2)
        else:
            return format_patent_markdown(result, detailed=True)
            
    except Exception as e:
        return f"❌ 조회 오류: {str(e)}"


@mcp.tool(
    name="kipris_get_citing_patents",
    annotations={
        "title": "인용 특허 조회",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def kipris_get_citing_patents(params: GetCitingPatentsInput) -> str:
    """특정 특허를 인용한 후행 특허들을 조회합니다.
    
    기준 특허의 출원번호를 입력하면, 해당 특허를 인용한 모든 후행 특허 목록을 
    반환합니다. 이를 통해 특허의 영향력과 기술 발전 흐름을 파악할 수 있습니다.
    
    Args:
        params (GetCitingPatentsInput): 조회 파라미터
            - application_number: 기준 특허의 출원번호 (필수)
            - response_format: 응답 형식 ('markdown' 또는 'json')
    
    Returns:
        str: 인용 특허 목록 (마크다운 또는 JSON 형식)
    
    Example:
        - 특정 특허를 인용한 후행 특허 찾기: application_number="1020180123456"
    
    Note:
        - 인용 특허가 많은 경우 해당 특허의 기술적 영향력이 큼을 의미합니다
        - 인용 유형(citation_type)을 통해 심사관 인용/출원인 인용 구분 가능
    """
    from mcp.server.fastmcp import Context
    ctx = Context.current()
    
    client = ctx.request_context.lifespan_state.get("kipris_client")
    if client is None:
        error = ctx.request_context.lifespan_state.get("init_error", "API 클라이언트 초기화 실패")
        return f"❌ 오류: {error}"
    
    app_num = params.application_number.replace("-", "")
    
    try:
        result = await client.get_citing_patents(app_num)
        
        if params.response_format == ResponseFormat.JSON:
            return json.dumps({
                "base_application_number": app_num,
                "citing_count": len(result),
                "citing_patents": result
            }, ensure_ascii=False, indent=2)
        else:
            return format_citing_patents_markdown(result, app_num)
            
    except Exception as e:
        return f"❌ 조회 오류: {str(e)}"


# =========================================================================
# Server Entry Point
# =========================================================================

def main():
    """서버 실행 진입점"""
    mcp.run()


if __name__ == "__main__":
    main()

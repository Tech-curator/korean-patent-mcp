"""
KIPRIS API Client for MCP Server
한국 특허정보 검색서비스 API 클라이언트
"""
import os
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import httpx
from dotenv import load_dotenv

load_dotenv()


@dataclass
class KiprisConfig:
    """KIPRIS API 설정"""
    api_key: str
    base_url: str = "http://plus.kipris.or.kr/openapi/rest"
    timeout: int = 30
    max_retries: int = 3
    
    @classmethod
    def from_env(cls) -> "KiprisConfig":
        """환경변수에서 설정 로드"""
        api_key = os.getenv("KIPRIS_API_KEY", "")
        if not api_key:
            raise ValueError(
                "KIPRIS_API_KEY 환경변수가 설정되지 않았습니다. "
                ".env 파일에 KIPRIS_API_KEY=your_key 형식으로 추가하세요."
            )
        return cls(api_key=api_key)


class KiprisAPIClient:
    """KIPRIS API 클라이언트"""
    
    # API 엔드포인트
    ENDPOINTS = {
        "applicant_search": "/patUtiModInfoSearchSevice/applicantNameSearchInfo",
        "application_search": "/patUtiModInfoSearchSevice/applicationNumberSearchInfo",
        "citing_info": "/CitingService/citingInfo",
        "patent_info": "/patUtiModInfoSearchSevice/applicationNumberSearchInfo",
        "cpc_info": "/patUtiModInfoSearchSevice/patentCpcInfo",
        "inventor_info": "/patUtiModInfoSearchSevice/patentInventorInfo",
        "reject_decision": "/IntermediateDocumentOPService/rejectDecisionInfo",
    }
    
    def __init__(self, config: Optional[KiprisConfig] = None):
        """
        초기화
        
        Args:
            config: KIPRIS API 설정 (None이면 환경변수에서 로드)
        """
        self.config = config or KiprisConfig.from_env()
        self.client = httpx.AsyncClient(timeout=self.config.timeout)
    
    async def close(self):
        """HTTP 클라이언트 종료"""
        await self.client.aclose()
    
    async def _make_request(
        self, 
        endpoint: str, 
        params: Dict[str, Any]
    ) -> Optional[ET.Element]:
        """
        API 요청 실행
        
        Args:
            endpoint: API 엔드포인트
            params: 요청 파라미터
            
        Returns:
            XML 루트 엘리먼트 또는 None
        """
        url = f"{self.config.base_url}{endpoint}"
        params["accessKey"] = self.config.api_key
        
        for attempt in range(self.config.max_retries):
            try:
                response = await self.client.get(url, params=params)
                if response.status_code == 200:
                    return ET.fromstring(response.content)
                else:
                    if attempt == self.config.max_retries - 1:
                        raise httpx.HTTPStatusError(
                            f"API 응답 오류: {response.status_code}",
                            request=response.request,
                            response=response
                        )
            except httpx.TimeoutException:
                if attempt == self.config.max_retries - 1:
                    raise
            except ET.ParseError as e:
                raise ValueError(f"XML 파싱 오류: {e}")
        
        return None
    
    # =========================================================================
    # Core Tools
    # =========================================================================
    
    async def search_patents_by_applicant(
        self,
        applicant_name: str,
        page: int = 1,
        page_size: int = 20,
        status: str = ""
    ) -> Dict[str, Any]:
        """
        출원인명으로 특허 검색
        
        Args:
            applicant_name: 출원인명 (예: "삼성전자", "충북대학교 산학협력단")
            page: 페이지 번호 (1부터 시작)
            page_size: 페이지당 결과 수 (최대 500)
            status: 상태 필터 (A: 공개, R: 등록, J: 거절, 빈값: 전체)
            
        Returns:
            검색 결과 딕셔너리
        """
        params = {
            "applicant": applicant_name,
            "docsStart": str(page),
            "docsCount": str(min(page_size, 500)),
            "patent": "true",
            "utility": "false",
            "lastvalue": status
        }
        
        root = await self._make_request(
            self.ENDPOINTS["applicant_search"], 
            params
        )
        
        if root is None:
            return {"patents": [], "total_count": 0, "page": page}
        
        # 전체 건수
        total_elem = root.find(".//TotalSearchCount")
        total_count = int(total_elem.text) if (total_elem is not None and total_elem.text) else 0
        
        # 특허 정보 추출
        patents = []
        for item in root.findall(".//PatentUtilityInfo"):
            patent = self._parse_patent_info(item)
            patents.append(patent)
        
        return {
            "patents": patents,
            "total_count": total_count,
            "page": page,
            "page_size": len(patents),
            "has_more": (page * page_size) < total_count,
            "next_page": page + 1 if (page * page_size) < total_count else None
        }
    
    async def get_patent_detail(
        self,
        application_number: str
    ) -> Optional[Dict[str, Any]]:
        """
        출원번호로 특허 상세 정보 조회
        
        Args:
            application_number: 출원번호 (예: "1020200123456")
            
        Returns:
            특허 상세 정보 딕셔너리
        """
        params = {
            "applicationNumber": application_number,
            "docsStart": "1"
        }
        
        root = await self._make_request(
            self.ENDPOINTS["patent_info"],
            params
        )
        
        if root is None:
            return None
        
        item = root.find(".//PatentUtilityInfo")
        if item is None:
            return None
        
        return self._parse_patent_info(item, detailed=True)
    
    async def get_citing_patents(
        self,
        application_number: str
    ) -> List[Dict[str, Any]]:
        """
        특정 특허를 인용한 후행 특허 조회
        
        Args:
            application_number: 기준 특허의 출원번호
            
        Returns:
            인용 특허 목록
        """
        params = {
            "standardCitationApplicationNumber": application_number
        }
        
        root = await self._make_request(
            self.ENDPOINTS["citing_info"],
            params
        )
        
        if root is None:
            return []
        
        citing_patents = []
        for item in root.findall(".//citingInfo"):
            citing_info = {
                "citing_application_number": self._get_text(item, "ApplicationNumber"),
                "standard_citation_number": self._get_text(item, "StandardCitationApplicationNumber"),
                "status_code": self._get_text(item, "StandardStatusCode"),
                "status_name": self._get_text(item, "StandardStatusCodeName"),
                "citation_type_code": self._get_text(item, "CitationLiteratureTypeCode"),
                "citation_type_name": self._get_text(item, "CitationLiteratureTypeCodeName"),
            }
            citing_patents.append(citing_info)
        
        return citing_patents
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _parse_patent_info(
        self, 
        item: ET.Element, 
        detailed: bool = False
    ) -> Dict[str, Any]:
        """특허 정보 XML 엘리먼트 파싱"""
        patent = {
            "application_number": self._get_text(item, "ApplicationNumber"),
            "application_date": self._get_text(item, "ApplicationDate"),
            "title": self._get_text(item, "InventionName"),
            "applicant": self._get_text(item, "Applicant"),
            "registration_status": self._get_text(item, "RegistrationStatus"),
        }
        
        # 공개 정보
        patent["opening_number"] = self._get_text(item, "OpeningNumber")
        patent["opening_date"] = self._get_text(item, "OpeningDate")
        
        # 등록 정보
        patent["registration_number"] = self._get_text(item, "RegistrationNumber")
        patent["registration_date"] = self._get_text(item, "RegistrationDate")
        
        if detailed:
            patent["abstract"] = self._get_text(item, "Abstract")
            patent["ipc_number"] = self._get_text(item, "InternationalpatentclassificationNumber")
        
        return patent
    
    @staticmethod
    def _get_text(element: ET.Element, tag: str) -> Optional[str]:
        """XML 엘리먼트에서 텍스트 추출"""
        child = element.find(tag)
        if child is not None and child.text:
            return child.text.strip()
        return None


# =========================================================================
# Future Works (Extended Tools) - TODO
# =========================================================================
# 
# 아래 기능들은 향후 구현 예정:
#
# 1. get_cpc_codes(application_number: str) -> List[str]
#    - CPC(협동특허분류) 코드 조회
#    - 엔드포인트: /patUtiModInfoSearchSevice/patentCpcInfo
#
# 2. get_inventors(application_number: str) -> List[str]
#    - 발명자 정보 조회
#    - 엔드포인트: /patUtiModInfoSearchSevice/patentInventorInfo
#
# 3. check_rejection_status(application_number: str) -> bool
#    - 특허 거절 여부 확인
#    - lastvalue='J' 파라미터로 조회
#
# 4. analyze_rejection_reason(b_app_num: str, p_numbers: set) -> Dict
#    - 거절결정서에서 선행특허 분석
#    - 엔드포인트: /IntermediateDocumentOPService/rejectDecisionInfo
#
# =========================================================================

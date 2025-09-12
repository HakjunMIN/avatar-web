import os
import uuid
import json
import logging
from typing import Dict, Any, Union
from openai import AzureOpenAI

try:
    from diagrams import Diagram, Cluster, Edge
    from diagrams.azure.compute import AppServices, FunctionApps, ContainerInstances, VM, ContainerApps, KubernetesServices   
    from diagrams.azure.database import DatabaseForPostgresqlServers, CosmosDb, SQLDatabases
    from diagrams.azure.storage import StorageAccounts, BlobStorage
    from diagrams.azure.network import LoadBalancers, ApplicationGateway, CDNProfiles, VirtualNetworks, Subnets, Firewall, FrontDoors
    
    from diagrams.azure.integration import ServiceBus, LogicApps, APIManagement
    from diagrams.azure.analytics import SynapseAnalytics, DataFactories, EventHubs
    from diagrams.azure.ml import MachineLearningServiceWorkspaces, CognitiveServices, AzureOpenAI as OpenAI
    from diagrams.azure.monitor import Monitor
    from diagrams.azure.security import KeyVaults, SecurityCenter, ApplicationSecurityGroups
    from diagrams.azure.devops import Devops
    from diagrams.onprem.client import Users
    DIAGRAMS_AVAILABLE = True
except ImportError:
    DIAGRAMS_AVAILABLE = False

azure_openai_endpoint = os.environ.get('AZURE_OPENAI_ENDPOINT')
azure_openai_api_key = os.environ.get('AZURE_OPENAI_API_KEY')
azure_openai_deployment_name = os.environ.get('AZURE_OPENAI_DEPLOYMENT_NAME')

# Logger 설정
logger = logging.getLogger(__name__)

class ArchitectureDiagramService:
    
    # Azure 서비스 목록 상수
    AZURE_SERVICES_DESCRIPTION = """사용 가능한 Azure 서비스들:
        - app_service: Azure App Service (웹 애플리케이션)
        - function_app: Azure Functions (서버리스 함수)
        - container_instances: Azure Container Instances
        - virtual_machines: Azure Virtual Machines
        - container_apps: Azure Container Apps
        - kubernetes_services: Azure Kubernetes Services
        - postgresql: Azure Database for PostgreSQL
        - cosmos_db: Azure Cosmos DB
        - sql_database: Azure SQL Database
        - storage_account: Azure Storage Account
        - blob_storage: Azure Blob Storage
        - load_balancer: Azure Load Balancer
        - application_gateway: Azure Application Gateway
        - cdn: Azure CDN
        - virtual_network: Azure Virtual Network
        - subnet: Azure Subnet
        - firewall: Azure Firewall
        - front_door: Azure Front Door
        - application_security_group: Azure Application Security Group
        - api_management: Azure API Management
        - service_bus: Azure Service Bus
        - event_hubs: Azure Event Hubs
        - logic_apps: Azure Logic Apps
        - synapse: Azure Synapse Analytics
        - data_factory: Azure Data Factory
        - ml_workspace: Azure Machine Learning
        - cognitive_services: Azure Cognitive Services
        - openai: Azure OpenAI
        - monitor: Azure Monitor
        - key_vault: Azure Key Vault
        - security_center: Azure Security Center
        - devops: Azure DevOps
        - users: Users/Clients"""
    
    def __init__(self):
        self.azure_openai = None
        if azure_openai_endpoint and azure_openai_api_key:
            self.azure_openai = AzureOpenAI(
                azure_endpoint=azure_openai_endpoint,
                api_version='2024-06-01',
                api_key=azure_openai_api_key
            )
        
        # Azure 서비스 매핑
        self.azure_services_map = {
            'app_service': AppServices,
            'function_app': FunctionApps,
            'container_instances': ContainerInstances,
            'container_apps': ContainerApps,
            'kubernetes_services': KubernetesServices,
            'virtual_machines': VM,
            'postgresql': DatabaseForPostgresqlServers,
            'cosmos_db': CosmosDb,
            'sql_database': SQLDatabases,
            'storage_account': StorageAccounts,
            'blob_storage': BlobStorage,
            'load_balancer': LoadBalancers,
            'application_gateway': ApplicationGateway,
            'cdn': CDNProfiles,
            'firewall': Firewall,
            'front_door': FrontDoors,
            'application_security_group': ApplicationSecurityGroups,
            'virtual_network': VirtualNetworks,
            'subnet': Subnets,
            'api_management': APIManagement,
            'service_bus': ServiceBus,
            'event_hubs': EventHubs,
            'logic_apps': LogicApps,
            'synapse': SynapseAnalytics,
            'data_factory': DataFactories,
            'ml_workspace': MachineLearningServiceWorkspaces,
            'cognitive_services': CognitiveServices,
            'openai': OpenAI,
            'key_vault': KeyVaults,
            'security_center': SecurityCenter,
            'devops': Devops,
            'users': Users,
            'monitor': Monitor
        }
    
    def _fix_json_format(self, json_str: str) -> str:
        """
        JSON 문자열의 일반적인 형식 문제를 수정합니다.
        - 단일 따옴표를 이중 따옴표로 변경
        - 후행 쉼표 제거
        """
        import re
        
        # 단일 따옴표를 이중 따옴표로 변경
        fixed_json = json_str.replace("'", '"')
        
        # 후행 쉼표 제거
        fixed_json = re.sub(r',(\s*[}\]])', r'\1', fixed_json)
        
        return fixed_json
    
    def _parse_json_safely(self, json_str: str, context: str = "") -> Dict[str, Any]:
        """
        JSON 문자열을 안전하게 파싱합니다. 실패시 형식 수정을 시도합니다.
        """
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON in {context}: {e}")
            try:
                fixed_json = self._fix_json_format(json_str)
                result = json.loads(fixed_json)
                logger.info(f"Successfully parsed JSON in {context} after fixing format issues")
                return result
            except json.JSONDecodeError as e2:
                logger.error(f"Still failed to parse JSON in {context} after fixing: {e2}")
                raise e2
    
    def _process_stream_response(self, stream_response) -> str:
        """
        스트림 응답을 처리하여 완전한 응답 텍스트를 반환합니다.
        
        Args:
            stream_response: Azure OpenAI 스트림 응답 객체
            
        Returns:
            str: 완전한 응답 텍스트
        """
        full_content = ""
        try:
            for chunk in stream_response:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, 'content') and delta.content is not None:
                        full_content += delta.content
                        # 실시간 로그 출력 (선택사항)
                        logger.debug(f"Stream chunk: {delta.content}")
            return full_content
        except Exception as e:
            logger.error(f"Error processing stream response: {e}")
            raise e
    
    def generate_architecture_diagram(self, requirements: str) -> Dict[str, Any]:
        """
        아키텍처 요구사항을 받아서 Azure Architecture Diagram을 생성합니다.
        
        Args:
            requirements: 자연어로 작성된 아키텍처 요구사항
            
        Returns:
            Dict containing diagram path and description
        """
        logger.info("Starting diagram generation")
        logger.debug(f"Requirements: {requirements}")
        
        try:
            # OpenAI를 사용하여 요구사항을 분석하고 다이어그램 구조 생성
            logger.info("Analyzing requirements with OpenAI")
            diagram_structure = self._analyze_requirements_with_openai(requirements)
            logger.debug(f"OpenAI analysis completed: {diagram_structure}")
            
            # 다이어그램 생성
            logger.info("Creating diagram")
            diagram_path = self._create_diagram(diagram_structure)
            logger.info(f"Diagram created at: {diagram_path}")
            
            # 상세 설명 생성
            logger.info("Generating description")
            description = self._generate_description(diagram_structure, requirements)
            logger.debug(f"Description generated, length: {len(description) if description else 0}")
            
            # 다이어그램과 설명을 포함한 포맷된 응답 생성
            formatted_description = self._format_description_with_diagram(description, diagram_path)
            
            result = {
                'success': True,
                'diagram_path': diagram_path,
                'description': formatted_description,
                'structure': diagram_structure,
                'diagram_tag': f'<DIAGRAM>{diagram_path}</DIAGRAM>'
            }
            
            logger.info("Diagram generation completed successfully")
            return result
            
        except Exception as e:
            logger.exception(f"Error during diagram generation: {str(e)}")
            
            return {
                'success': False,
                'error': str(e),
                'diagram_path': None,
                'structure': None,
                'description': None
            }
    
    def modify_architecture_diagram(self, structure_json: Union[str, Dict[str, Any]], requirements: str) -> Dict[str, Any]:
        """
        기존 아키텍처를 수정하는 기능입니다.
        
        Args:
            structure_json: 기존 아키텍처 구조 (JSON 문자열 또는 딕셔너리)
            requirements: 수정 요구사항
            
        Returns:
            Dict containing modified diagram path and description (generate_architecture_diagram과 동일한 형태)
        """
        logger.info("Starting architecture modification")
        logger.debug(f"Structure JSON: {structure_json}")
        logger.debug(f"Requirements: {requirements}")
        
        try:
            # 기존 구조가 비어있는 경우 새로 생성
            if not structure_json:
                logger.info("Structure JSON is empty, generating new architecture")
                return self.generate_architecture_diagram(requirements)
            
            # structure_json이 이미 dict인 경우와 string인 경우 모두 처리
            if isinstance(structure_json, dict):
                # 이미 딕셔너리인 경우
                previous_structure_dict = structure_json
                logger.debug(f"Using existing dict structure: {previous_structure_dict}")
            elif isinstance(structure_json, str):
                # 문자열인 경우 strip() 체크 후 파싱
                if structure_json.strip() == "":
                    logger.info("Structure JSON string is empty, generating new architecture")
                    return self.generate_architecture_diagram(requirements)
                
                try:
                    previous_structure_dict = self._parse_json_safely(structure_json, "previous structure")
                    logger.debug(f"Parsed previous structure: {previous_structure_dict}")
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse structure JSON even after fixing: {e}")
                    logger.info("Falling back to new architecture generation")
                    return self.generate_architecture_diagram(requirements)
            else:
                logger.warning(f"Invalid structure_json type: {type(structure_json)}")
                logger.info("Falling back to new architecture generation")
                return self.generate_architecture_diagram(requirements)
            
            # OpenAI를 사용하여 기존 구조와 요구사항을 분석하고 수정된 다이어그램 구조 생성
            logger.info("Analyzing modification requirements with OpenAI")
            modified_structure = self._analyze_modification_with_openai(previous_structure_dict, requirements)
            logger.debug(f"OpenAI modification analysis completed: {modified_structure}")
            
            # 수정된 다이어그램 생성
            logger.info("Creating modified diagram")
            diagram_path = self._create_diagram(modified_structure)
            logger.info(f"Modified diagram created at: {diagram_path}")
            
            # 수정에 대한 상세 설명 생성
            logger.info("Generating modification description")
            description = self._generate_modification_description(previous_structure_dict, modified_structure, requirements)
            logger.debug(f"Modification description generated, length: {len(description) if description else 0}")
            
            # 다이어그램과 설명을 포함한 포맷된 응답 생성
            formatted_description = self._format_description_with_diagram(description, diagram_path)
            
            result = {
                'success': True,
                'diagram_path': diagram_path,
                'description': formatted_description,
                'structure': modified_structure,
                'diagram_tag': f'<DIAGRAM>{diagram_path}</DIAGRAM>'
            }
            
            logger.info("Architecture modification completed successfully")
            return result
            
        except Exception as e:
            logger.exception(f"Error during architecture modification: {str(e)}")
            
            return {
                'success': False,
                'error': str(e),
                'diagram_path': None,
                'structure': None,
                'description': None
            }
    
    def _analyze_requirements_with_openai(self, requirements: str) -> Dict[str, Any]:
        """OpenAI를 사용하여 요구사항을 분석하고 다이어그램 구조를 생성합니다."""
        
        system_prompt = f"""
        당신은 Azure 아키텍처 전문가입니다. 사용자의 요구사항을 분석하여 Azure 서비스를 사용한 아키텍처 다이어그램 구조를 JSON으로 생성해주세요.

        {self.AZURE_SERVICES_DESCRIPTION}

        JSON 응답 형식:
        {{
            "title": "다이어그램 제목",
            "components": [
                {{
                    "id": "component_id",
                    "service": "service_name",
                    "label": "Component Label",
                    "cluster": "cluster_name" (선택사항)
                }}
            ],
            "connections": [
                {{
                    "from": "component_id1",
                    "to": "component_id2",
                    "label": "connection_label" (선택사항)
                }}
            ],
            "clusters": [
                {{
                    "name": "cluster_name",
                    "label": "Cluster Label"
                }}
            ]
        }}
        """
        
        user_prompt = f"다음 아키텍처 요구사항을 분석하여 Azure 다이어그램 구조를 JSON으로 생성해주세요:\n\n{requirements}"
        
        logger.debug("Checking OpenAI configuration")
        if not self.azure_openai:
            # OpenAI가 설정되지 않은 경우 기본 구조 반환
            logger.warning("OpenAI not configured, using default structure")
            return self._get_default_structure()
        
        try:
            logger.debug("Calling OpenAI API for requirements analysis")
            stream_response = self.azure_openai.chat.completions.create(
                model=azure_openai_deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                stream=True
            )
            
            logger.debug("OpenAI API call completed, processing stream")
            content = self._process_stream_response(stream_response)
            logger.debug(f"OpenAI response content: {content}")
            
            # JSON 추출 - 더 견고한 방법으로 개선
            try:
                # 여러 방법으로 JSON 추출 시도
                json_str = None
                
                # 방법 1: 첫 번째 { 부터 마지막 } 까지
                start_idx = content.find('{')
                if start_idx != -1:
                    # 중괄호 매칭을 사용하여 올바른 JSON 끝 찾기
                    brace_count = 0
                    end_idx = start_idx
                    for i, char in enumerate(content[start_idx:], start_idx):
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_idx = i + 1
                                break
                    json_str = content[start_idx:end_idx]
                
                # 방법 2: JSON 코드 블록 찾기
                if not json_str or json_str == '{}':
                    import re
                    json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(1)
                
                # 방법 3: 백틱 없는 JSON 블록
                if not json_str or json_str == '{}':
                    json_match = re.search(r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})', content, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(1)
                
                if not json_str:
                    logger.error("Could not extract JSON from OpenAI response")
                    logger.error(f"Response content: {content}")
                    return self._get_default_structure()
                
                logger.debug(f"Extracted JSON: {json_str}")
                
                # JSON 파싱 시도
                result = self._parse_json_safely(json_str, "OpenAI response")
                logger.debug(f"Parsed JSON structure: {result}")
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse extracted JSON even after fixing: {e}")
                logger.error(f"Problematic JSON: {json_str}")
                logger.error(f"Full OpenAI response: {content}")
                return self._get_default_structure()
            
        except Exception as e:
            logger.exception(f"OpenAI 분석 오류: {e}")
            logger.info("Falling back to default structure")
            return self._get_default_structure()
    
    def _analyze_modification_with_openai(self, previous_structure: Dict[str, Any], requirements: str) -> Dict[str, Any]:
        """OpenAI를 사용하여 기존 아키텍처 구조를 분석하고 변경 요구사항에 따라 수정된 구조를 생성합니다."""
        
        system_prompt = f"""
        당신은 Azure 아키텍처 전문가입니다. 기존 아키텍처 구조와 변경 요구사항을 분석하여 수정된 Azure 아키텍처 다이어그램 구조를 JSON으로 생성해주세요.

        {self.AZURE_SERVICES_DESCRIPTION}

        변경 요구사항을 기존 아키텍처에 적용하여 수정된 구조를 생성해주세요.
        - 기존 구성 요소들을 최대한 유지하면서 필요한 변경사항만 적용
        - 새로운 구성 요소가 필요하면 추가
        - 불필요한 구성 요소가 있으면 제거
        - 연결 관계도 요구사항에 맞게 수정

        JSON 응답 형식:
        {{
            "title": "다이어그램 제목",
            "components": [
                {{
                    "id": "component_id",
                    "service": "service_name",
                    "label": "Component Label",
                    "cluster": "cluster_name" (선택사항)
                }}
            ],
            "connections": [
                {{
                    "from": "component_id1",
                    "to": "component_id2",
                    "label": "connection_label" (선택사항)
                }}
            ],
            "clusters": [
                {{
                    "name": "cluster_name",
                    "label": "Cluster Label"
                }}
            ]
        }}
        """
        
        user_prompt = f"""
        기존 아키텍처 구조:
        {json.dumps(previous_structure, ensure_ascii=False, indent=2)}
        
        변경 요구사항:
        {requirements}
        
        위 기존 아키텍처에 변경 요구사항을 적용하여 수정된 Azure 다이어그램 구조를 JSON으로 생성해주세요.
        """
        
        logger.debug("Checking OpenAI configuration for modification")
        if not self.azure_openai:
            # OpenAI가 설정되지 않은 경우 기존 구조에 기본적인 수정 적용
            logger.warning("OpenAI not configured, applying basic modifications to existing structure")
            return self._apply_basic_modifications(previous_structure, requirements)
        
        try:
            logger.debug("Calling OpenAI API for modification analysis")
            stream_response = self.azure_openai.chat.completions.create(
                model=azure_openai_deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                stream=True
            )
            
            logger.debug("OpenAI API call completed for modification, processing stream")
            content = self._process_stream_response(stream_response)
            logger.debug(f"OpenAI modification response content: {content}")
            
            # JSON 추출
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            json_str = content[start_idx:end_idx]
            
            logger.debug(f"Extracted modification JSON: {json_str}")
            
            result = self._parse_json_safely(json_str, "modification analysis")
            logger.debug(f"Parsed modification JSON structure: {result}")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse modification JSON even after fixing: {e}")
            logger.info("Falling back to basic modification")
            return self._apply_basic_modifications(previous_structure, requirements)
        except Exception as e:
            logger.exception(f"OpenAI 수정 분석 오류: {e}")
            logger.info("Falling back to basic modification")
            return self._apply_basic_modifications(previous_structure, requirements)
    
    def _apply_basic_modifications(self, previous_structure: Dict[str, Any], requirements: str) -> Dict[str, Any]:
        """OpenAI를 사용할 수 없는 경우 기본적인 수정을 적용합니다."""
        logger.info("Applying basic modifications to existing structure")
        
        # 기존 구조를 복사하여 기본적인 수정 적용
        modified_structure = json.loads(json.dumps(previous_structure))
        
        # 제목에 "Modified" 추가
        original_title = modified_structure.get('title', 'Azure Architecture')
        modified_structure['title'] = f"Modified {original_title}"
        
        # 요구사항에 따라 간단한 로직으로 구성 요소 추가
        # 예: "데이터베이스"가 언급되면 데이터베이스 추가
        requirements_lower = requirements.lower()
        
        existing_component_ids = {comp['id'] for comp in modified_structure.get('components', [])}
        
        if 'database' in requirements_lower or '데이터베이스' in requirements_lower:
            if 'database' not in existing_component_ids:
                new_component = {
                    "id": "database",
                    "service": "sql_database",
                    "label": "SQL Database",
                    "cluster": "data"
                }
                modified_structure.setdefault('components', []).append(new_component)
                
                # 데이터 클러스터 추가
                existing_clusters = {cluster['name'] for cluster in modified_structure.get('clusters', [])}
                if 'data' not in existing_clusters:
                    modified_structure.setdefault('clusters', []).append({
                        "name": "data",
                        "label": "Data Services"
                    })
        
        logger.debug(f"Basic modifications applied: {modified_structure}")
        return modified_structure
    
    def _get_default_structure(self) -> Dict[str, Any]:
        """기본 아키텍처 구조를 반환합니다."""
        return {
            "title": "Azure Web Application Architecture",
            "components": [
                {"id": "users", "service": "users", "label": "Users"},
                {"id": "app_gateway", "service": "application_gateway", "label": "Application Gateway"},
                {"id": "web_app", "service": "app_service", "label": "Web App", "cluster": "compute"},
                {"id": "api", "service": "function_app", "label": "API Functions", "cluster": "compute"},
                {"id": "database", "service": "sql_database", "label": "SQL Database", "cluster": "data"},
                {"id": "storage", "service": "blob_storage", "label": "Blob Storage", "cluster": "data"}
            ],
            "connections": [
                {"from": "users", "to": "app_gateway"},
                {"from": "app_gateway", "to": "web_app"},
                {"from": "web_app", "to": "api"},
                {"from": "api", "to": "database"},
                {"from": "api", "to": "storage"}
            ],
            "clusters": [
                {"name": "compute", "label": "Compute Services"},
                {"name": "data", "label": "Data Services"}
            ]
        }
    
    def _create_diagram(self, structure: Dict[str, Any]) -> str:
        """다이어그램 구조를 바탕으로 실제 다이어그램을 생성합니다."""
        
        logger.info("Starting diagram creation")
        logger.debug(f"Structure: {structure}")
        
        if not DIAGRAMS_AVAILABLE:
            logger.error("Error: diagrams library not available")
            raise ImportError("diagrams 라이브러리가 설치되지 않았습니다. 'pip install diagrams' 명령어로 설치해주세요.")
        
        # .temp 디렉토리에 다이어그램 생성
        diagram_id = str(uuid.uuid4())
        output_dir = os.path.join(os.getcwd(), '.temp')
        os.makedirs(output_dir, exist_ok=True)
        diagram_name = f"azure_architecture_{diagram_id}"
        
        logger.debug(f"Generated diagram ID: {diagram_id}")
        logger.debug(f"Output directory: {output_dir}")
        logger.debug(f"Diagram name: {diagram_name}")
        
        try:
            with Diagram(
                structure.get('title', 'Azure Architecture'),
                filename=os.path.join(output_dir, diagram_name),
                show=False,
                direction="TB"
            ):
                # 컴포넌트 생성
                components = {}
                clusters = {}
                
                logger.debug(f"Creating clusters: {structure.get('clusters', [])}")
                # 클러스터 생성
                for cluster_info in structure.get('clusters', []):
                    cluster_name = cluster_info['name']
                    cluster_label = cluster_info['label']
                    clusters[cluster_name] = Cluster(cluster_label)
                    logger.debug(f"Created cluster: {cluster_name} ({cluster_label})")
                
                logger.debug(f"Creating components: {structure.get('components', [])}")
                # 컴포넌트 생성
                for component in structure.get('components', []):
                    comp_id = component['id']
                    service = component['service']
                    label = component['label']
                    cluster_name = component.get('cluster')
                    
                    logger.debug(f"Processing component: {comp_id} ({service})")
                    
                    if service in self.azure_services_map:
                        service_class = self.azure_services_map[service]
                        
                        if cluster_name and cluster_name in clusters:
                            logger.debug(f"Adding component {comp_id} to cluster {cluster_name}")
                            with clusters[cluster_name]:
                                components[comp_id] = service_class(label)
                        else:
                            logger.debug(f"Adding component {comp_id} without cluster")
                            components[comp_id] = service_class(label)
                    else:
                        logger.warning(f"Unknown service type: {service}")
                
                logger.debug(f"Creating connections: {structure.get('connections', [])}")
                # 연결 생성
                for connection in structure.get('connections', []):
                    from_comp = connection['from']
                    to_comp = connection['to']
                    label = connection.get('label', '')
                    
                    logger.debug(f"Processing connection: {from_comp} -> {to_comp}")
                    
                    if from_comp in components and to_comp in components:
                        if label:
                            components[from_comp] >> Edge(label=label) >> components[to_comp]
                            logger.debug(f"Created labeled connection: {from_comp} -> {to_comp} ({label})")
                        else:
                            components[from_comp] >> components[to_comp]
                            logger.debug(f"Created connection: {from_comp} -> {to_comp}")
                    else:
                        logger.warning(f"Invalid connection - missing components: {from_comp} -> {to_comp}")
            
            # 생성된 PNG 파일 경로 - 상대 경로로 반환
            png_path = f".temp/{diagram_name}.png"
            logger.info(f"Diagram creation completed: {png_path}")
            
            # 파일이 실제로 생성되었는지 확인
            full_path = os.path.join(output_dir, f"{diagram_name}.png")
            if os.path.exists(full_path):
                logger.debug(f"Diagram file verified: {full_path}")
            else:
                logger.warning(f"Diagram file not found: {full_path}")
            
            return png_path
            
        except Exception as e:
            logger.exception(f"Error during diagram creation: {str(e)}")
            raise
    
    def _generate_description(self, structure: Dict[str, Any], requirements: str) -> str:
        """다이어그램에 대한 상세 설명을 생성합니다."""
        
        system_prompt = """
        당신은 Azure 아키텍처 전문가입니다. 주어진 아키텍처 다이어그램 구조와 원래 요구사항을 바탕으로 
        상세한 설명을 작성해주세요. 다음 내용을 포함해야 합니다:

        1. 아키텍처 개요
        2. 주요 구성 요소 설명
        3. 데이터 흐름 설명
        4. 보안 고려사항
        5. 확장성 및 가용성 고려사항
        6. 비용 최적화 방안

        한국어로 작성해주세요.
        """
        
        user_prompt = f"""
        원래 요구사항: {requirements}
        
        생성된 아키텍처 구조:
        {json.dumps(structure, ensure_ascii=False, indent=2)}
        
        위 정보를 바탕으로 상세한 아키텍처 설명을 작성해주세요.
        """
        
        if not self.azure_openai:
            return self._get_default_description(structure)
        
        try:
            stream_response = self.azure_openai.chat.completions.create(
                model=azure_openai_deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                stream=True
            )
            
            return self._process_stream_response(stream_response)
            
        except Exception as e:
            print(f"설명 생성 오류: {e}")
            return self._get_default_description(structure)
    
    def _generate_modification_description(self, previous_structure: Dict[str, Any], modified_structure: Dict[str, Any], requirements: str) -> str:
        """수정된 다이어그램에 대한 상세 설명을 생성합니다."""
        
        system_prompt = """
        당신은 Azure 아키텍처 전문가입니다. 기존 아키텍처 구조, 수정된 아키텍처 구조, 그리고 변경 요구사항을 바탕으로 
        수정 사항에 대한 상세한 설명을 작성해주세요. 다음 내용을 포함해야 합니다:

        1. 수정 개요 (무엇이 변경되었는지)
        2. 변경된 구성 요소 설명
        3. 새로 추가된 구성 요소 (있는 경우)
        4. 제거된 구성 요소 (있는 경우)
        5. 변경된 데이터 흐름 설명
        6. 수정으로 인한 이점
        7. 추가 고려사항

        한국어로 작성해주세요.
        """
        
        user_prompt = f"""
        변경 요구사항: {requirements}
        
        기존 아키텍처 구조:
        {json.dumps(previous_structure, ensure_ascii=False, indent=2)}
        
        수정된 아키텍처 구조:
        {json.dumps(modified_structure, ensure_ascii=False, indent=2)}
        
        위 정보를 바탕으로 아키텍처 수정 사항에 대한 상세한 설명을 작성해주세요.
        """
        
        if not self.azure_openai:
            return self._get_default_modification_description(previous_structure, modified_structure, requirements)
        
        try:
            stream_response = self.azure_openai.chat.completions.create(
                model=azure_openai_deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                stream=True
            )
            
            return self._process_stream_response(stream_response)
            
        except Exception as e:
            print(f"수정 설명 생성 오류: {e}")
            return self._get_default_modification_description(previous_structure, modified_structure, requirements)
    
    def _get_default_modification_description(self, previous_structure: Dict[str, Any], modified_structure: Dict[str, Any], requirements: str) -> str:
        """기본 수정 설명을 생성합니다."""
        modified_title = modified_structure.get('title', 'Modified Azure Architecture')
        
        # 변경사항 분석
        prev_components = {comp['id']: comp for comp in previous_structure.get('components', [])}
        mod_components = {comp['id']: comp for comp in modified_structure.get('components', [])}
        
        added_components = []
        removed_components = []
        
        for comp_id in mod_components:
            if comp_id not in prev_components:
                added_components.append(mod_components[comp_id]['label'])
        
        for comp_id in prev_components:
            if comp_id not in mod_components:
                removed_components.append(prev_components[comp_id]['label'])
        
        description = f"""# {modified_title}

## 수정 개요
기존 아키텍처에 다음과 같은 변경 요구사항이 적용되었습니다: {requirements}

## 변경 사항
"""
        
        if added_components:
            description += """
### 추가된 구성 요소
"""
            for component in added_components:
                description += f"- **{component}**: 새로 추가된 서비스\n"
        
        if removed_components:
            description += """
### 제거된 구성 요소
"""
            for component in removed_components:
                description += f"- **{component}**: 제거된 서비스\n"
        
        if not added_components and not removed_components:
            description += "- 기존 구성 요소의 설정 및 연결이 수정되었습니다.\n"
        
        description += """
## 현재 구성 요소
"""
        
        for component in modified_structure.get('components', []):
            service = component.get('service', '')
            label = component.get('label', '')
            description += f"- **{label}**: {service} 서비스\n"
        
        description += """
## 수정으로 인한 이점
- 요구사항에 맞는 최적화된 아키텍처 구성
- 향상된 성능과 확장성
- 비용 효율적인 리소스 활용
"""
        
        return description
    
    def _get_default_description(self, structure: Dict[str, Any]) -> str:
        """기본 설명을 생성합니다."""
        title = structure.get('title', 'Azure Architecture')
        components = structure.get('components', [])
        
        description = f"""# {title}

## 아키텍처 개요
이 아키텍처는 Azure 클라우드 서비스를 활용한 현대적인 웹 애플리케이션 구조입니다.

## 주요 구성 요소
"""
        
        for component in components:
            service = component.get('service', '')
            label = component.get('label', '')
            description += f"- **{label}**: {service} 서비스를 사용한 구성 요소\n"
        
        description += """
## 특징
- 높은 가용성과 확장성을 제공하는 클라우드 네이티브 아키텍처
- Azure의 관리형 서비스를 활용한 운영 부담 최소화
- 보안과 성능을 고려한 네트워크 구성
"""
        
        return description
    
    def _format_description_with_diagram(self, description: str, diagram_path: str) -> str:
        """설명과 다이어그램을 포함한 포맷된 응답을 생성합니다."""
        
        diagram_tag = f'<DIAGRAM>{diagram_path}</DIAGRAM>'
        
        # 설명 앞에 다이어그램 태그를 추가
        formatted_description = f"{diagram_tag}\n\n{description}"
        
        return formatted_description

    def generate_bicep_infrastructure(self, structure_json: str) -> Dict[str, Any]:
        """
        아키텍처 구조 JSON을 받아서 Azure Bicep 인프라 코드를 생성합니다.
        
        Args:
            structure_json: 아키텍처 구조 JSON 문자열
            
        Returns:
            Dict containing bicep code and deployment information
        """
        logger.info("Starting Bicep infrastructure code generation")
        logger.info(f"Structure JSON received (first 500 chars): {structure_json[:500] if structure_json else 'None'}")
        logger.info(f"Structure JSON length: {len(structure_json) if structure_json else 0} characters")
        
        try:
            # JSON 파싱
            # Check for common JSON formatting issues
            if not structure_json or not structure_json.strip():
                logger.error("Empty structure JSON provided")
                return {
                    'success': False,
                    'error': 'Empty JSON structure provided',
                    'bicep_code': None,
                    'deployment_guide': None
                }
            
            # Clean up the JSON string
            structure_json = structure_json.strip()
            
            # Remove any potential BOM or invisible characters
            import codecs
            if structure_json.startswith(codecs.BOM_UTF8.decode('utf-8')):
                structure_json = structure_json[1:]
                
            # Log the exact JSON around the error position if possible
            logger.info(f"Attempting to parse JSON: {structure_json}")
            
            try:
                structure = self._parse_json_safely(structure_json, "bicep generation")
                logger.debug(f"Parsed structure: {structure}")
                
                # Validate structure format
                if not isinstance(structure, dict):
                    logger.error(f"Structure is not a dictionary: {type(structure)}")
                    return {
                        'success': False,
                        'error': f'Structure must be a dictionary, got {type(structure)}',
                        'bicep_code': None,
                        'deployment_guide': None
                    }
                
                # Ensure required fields exist and are the right type
                components = structure.get('components', [])
                if not isinstance(components, list):
                    logger.warning(f"Components field is not a list, converting from {type(components)}")
                    structure['components'] = [components] if components else []
                    
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse structure JSON even after fixing: {e}")
                return {
                    'success': False,
                    'error': f'Invalid JSON format: {str(e)}',
                    'bicep_code': None,
                    'deployment_guide': None
                }
            
            # OpenAI를 사용하여 Bicep 코드 생성
            logger.info("Generating Bicep code with OpenAI")
            bicep_result = self._generate_bicep_with_openai(structure)
            
            if not bicep_result:
                return {
                    'success': False,
                    'error': 'Failed to generate Bicep code',
                    'bicep_code': None,
                    'deployment_guide': None
                }
            
            # 배포 가이드 생성
            deployment_guide = self._generate_deployment_guide(structure)
            
            result = {
                'success': True,
                'bicep_code': bicep_result['bicep_code'],
                'parameters_file': bicep_result.get('parameters_file', ''),
                'deployment_guide': deployment_guide,
                'resource_count': len(structure.get('components', []))
            }
            
            logger.info("Bicep infrastructure code generation completed successfully")
            return result
            
        except Exception as e:
            logger.exception(f"Error during Bicep code generation: {str(e)}")
            
            return {
                'success': False,
                'error': str(e),
                'bicep_code': None,
                'deployment_guide': None
            }

    def _generate_bicep_with_openai(self, structure: Dict[str, Any]) -> Dict[str, str]:
        """
        OpenAI를 사용하여 아키텍처 구조로부터 Bicep 코드를 생성합니다.
        """
        if not self.azure_openai:
            logger.error("Azure OpenAI client not configured")
            return None
        
        # 아키텍처 구조를 Bicep 생성 프롬프트로 변환
        bicep_prompt = self._create_bicep_generation_prompt(structure)
        
        try:
            stream_response = self.azure_openai.chat.completions.create(
                model=azure_openai_deployment_name,
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 Azure Bicep 인프라 코드 생성 전문가입니다. 주어진 아키텍처 구조를 분석하여 완전하고 배포 가능한 Bicep 코드를 생성해주세요. Azure 모범 사례를 따르고, 보안, 가용성, 확장성을 고려한 코드를 작성해주세요."
                    },
                    {
                        "role": "user", 
                        "content": bicep_prompt
                    }
                ],
                max_tokens=4000,
                temperature=0.1,
                stream=True
            )
            
            bicep_content = self._process_stream_response(stream_response)
            logger.debug(f"Generated Bicep content: {bicep_content}")
            
            # Bicep 코드와 파라미터 파일 분리
            return self._parse_bicep_response(bicep_content)
            
        except Exception as e:
            logger.error(f"Error calling Azure OpenAI for Bicep generation: {e}")
            return None

    def _create_bicep_generation_prompt(self, structure: Dict[str, Any]) -> str:
        """
        아키텍처 구조를 Bicep 생성 프롬프트로 변환합니다.
        """
        # Validate and extract structure components
        components = structure.get('components', [])
        connections = structure.get('connections', [])
        title = structure.get('title', 'Azure Infrastructure')
        
        # Log structure for debugging
        logger.debug(f"Components type: {type(components)}, value: {components}")
        logger.debug(f"Connections type: {type(connections)}, value: {connections}")
        
        # Ensure components is a list
        if not isinstance(components, list):
            logger.warning(f"Components is not a list, got {type(components)}. Converting to list.")
            components = [components] if components else []
        
        # Ensure connections is a list
        if not isinstance(connections, list):
            logger.warning(f"Connections is not a list, got {type(connections)}. Converting to list.")
            connections = [connections] if connections else []
        
        prompt = f"""다음 아키텍처 구조를 기반으로 Azure Bicep 인프라 코드를 생성해주세요:

# 프로젝트: {title}

## 구성 요소:
"""
        
        for i, component in enumerate(components):
            # Handle case where component might be a string instead of dict
            if isinstance(component, str):
                # If component is a string, treat it as both service and label
                service = component
                label = component
            elif isinstance(component, dict):
                service = component.get('service', '')
                label = component.get('label', '')
            else:
                # Skip invalid component types
                logger.warning(f"Invalid component type at index {i}: {type(component)}")
                continue
            prompt += f"{i+1}. {label} ({service})\n"
        
        if connections:
            prompt += "\n## 연결 관계:\n"
            for connection in connections:
                # Handle case where connection might not be a dict
                if isinstance(connection, dict):
                    source = connection.get('source', connection.get('from', ''))
                    target = connection.get('target', connection.get('to', ''))
                elif isinstance(connection, str):
                    # If connection is a string, skip it or handle as needed
                    logger.warning(f"Connection is string instead of dict: {connection}")
                    continue
                else:
                    logger.warning(f"Invalid connection type: {type(connection)}")
                    continue
                
                if source and target:
                    prompt += f"- {source} → {target}\n"
        
        prompt += f"""

## 요구사항:
1. **Bicep 모범 사례 준수**:
   - 리소스 명명 규칙 적용 (prefix, suffix, 환경별 구분)
   - 매개변수와 변수 적절히 사용
   - 태그를 활용한 리소스 관리
   - User-Defined Types 활용
   - @secure() 데코레이터 사용

2. **보안 고려사항**:
   - Managed Identity 사용
   - Key Vault 통합
   - 네트워크 보안 그룹 설정
   - HTTPS/TLS 강제

3. **운영 고려사항**:
   - 모니터링 및 로깅 설정
   - 백업 및 재해 복구
   - 자동 스케일링 구성
   - 비용 최적화

4. **출력 형식**:
   - main.bicep: 메인 인프라 코드
   - main.bicepparam: 매개변수 파일
   - 각 파일을 명확하게 구분하여 출력

다음 서비스 매핑을 참고하세요:
{self.AZURE_SERVICES_DESCRIPTION}

완전하고 배포 가능한 Bicep 코드를 생성해주세요. 각 파일은 ```bicep 또는 ```bicepparam 코드 블록으로 구분하여 출력해주세요."""
        
        return prompt

    def _parse_bicep_response(self, bicep_content: str) -> Dict[str, str]:
        """
        OpenAI 응답에서 Bicep 코드와 파라미터 파일을 분리합니다.
        """
        import re
        
        result = {
            'bicep_code': '',
            'parameters_file': ''
        }
        
        # Bicep 메인 파일 추출
        bicep_pattern = r'```bicep\n(.*?)\n```'
        bicep_matches = re.findall(bicep_pattern, bicep_content, re.DOTALL)
        if bicep_matches:
            result['bicep_code'] = bicep_matches[0].strip()
        
        # 파라미터 파일 추출
        param_pattern = r'```bicepparam\n(.*?)\n```'
        param_matches = re.findall(param_pattern, bicep_content, re.DOTALL)
        if param_matches:
            result['parameters_file'] = param_matches[0].strip()
        
        # 코드 블록이 없는 경우 전체 응답을 bicep_code로 사용
        if not result['bicep_code'] and not result['parameters_file']:
            result['bicep_code'] = bicep_content.strip()
        
        return result

    def _generate_deployment_guide(self, structure: Dict[str, Any]) -> str:
        """
        배포 가이드를 생성합니다.
        """
        title = structure.get('title', 'Azure Infrastructure')
        components_count = len(structure.get('components', []))
        
        guide = f"""# {title} 배포 가이드

## 배포 준비사항

### 1. 사전 요구사항
- Azure CLI 또는 Azure PowerShell 설치
- Azure 구독에 대한 기여자 권한
- Bicep CLI 설치 (`az bicep install`)

### 2. 리소스 그룹 생성
```bash
az group create --name rg-{title.lower().replace(' ', '-')} --location koreacentral
```

### 3. 배포 실행

#### Azure CLI 사용:
```bash
# 매개변수 파일이 있는 경우
az deployment group create \\
  --resource-group rg-{title.lower().replace(' ', '-')} \\
  --template-file main.bicep \\
  --parameters main.bicepparam

# 매개변수를 직접 전달하는 경우
az deployment group create \\
  --resource-group rg-{title.lower().replace(' ', '-')} \\
  --template-file main.bicep \\
  --parameters environmentName=prod location=koreacentral
```

#### Azure PowerShell 사용:
```powershell
New-AzResourceGroupDeployment `
  -ResourceGroupName "rg-{title.lower().replace(' ', '-')}" `
  -TemplateFile "main.bicep" `
  -TemplateParameterFile "main.bicepparam"
```

## 배포 후 확인사항

### 1. 리소스 상태 확인
```bash
az resource list --resource-group rg-{title.lower().replace(' ', '-')} --output table
```

### 2. 연결 테스트
- 웹 애플리케이션 엔드포인트 접근 확인
- 데이터베이스 연결 테스트
- API 엔드포인트 동작 확인

### 3. 모니터링 설정
- Azure Monitor 대시보드 확인
- 알림 규칙 설정
- 로그 분석 쿼리 설정

## 예상 배포 시간
- 리소스 수: {components_count}개
- 예상 소요시간: {components_count * 3}-{components_count * 5}분

## 비용 예상
배포된 리소스의 월간 예상 비용은 Azure 가격 계산기를 통해 확인하세요:
https://azure.microsoft.com/pricing/calculator/

## 문제 해결
- 권한 오류: 구독에 대한 기여자 권한 확인
- 리소스 이름 충돌: 매개변수 파일에서 고유한 이름 접미사 설정
- 배포 실패: `az deployment group show` 명령으로 오류 세부사항 확인"""
        
        return guide

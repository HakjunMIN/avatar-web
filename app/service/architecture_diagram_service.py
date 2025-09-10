import os
import uuid
import json
import logging
from typing import Dict, Any
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
    
    def modify_architecture_diagram(self, previous_structure: str, requirements: str) -> Dict[str, Any]:
        """
        기존 아키텍처를 수정하는 기능입니다.
        
        Args:
            previous_structure: 기존 아키텍처 구조 JSON 문자열 (chat.html의 structureJson에서 가져옴)
            requirements: 수정 요구사항
            
        Returns:
            Dict containing modified diagram path and description (generate_architecture_diagram과 동일한 형태)
        """
        logger.info("Starting architecture modification")
        logger.debug(f"Previous structure: {previous_structure}")
        logger.debug(f"Requirements: {requirements}")
        
        try:
            # 기존 구조가 비어있는 경우 새로 생성
            if not previous_structure or previous_structure.strip() == "":
                logger.info("Previous structure is empty, generating new architecture")
                return self.generate_architecture_diagram(requirements)
            
            # 기존 구조 파싱
            try:
                previous_structure_dict = json.loads(previous_structure)
                logger.debug(f"Parsed previous structure: {previous_structure_dict}")
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse previous structure JSON: {e}")
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
            response = self.azure_openai.chat.completions.create(
                model=azure_openai_deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
            )
            
            logger.debug("OpenAI API call completed")
            content = response.choices[0].message.content
            logger.debug(f"OpenAI response content: {content}")
            
            # JSON 추출
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            json_str = content[start_idx:end_idx]
            
            logger.debug(f"Extracted JSON: {json_str}")
            
            result = json.loads(json_str)
            logger.debug(f"Parsed JSON structure: {result}")
            return result
            
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
            response = self.azure_openai.chat.completions.create(
                model=azure_openai_deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
            )
            
            logger.debug("OpenAI API call completed for modification")
            content = response.choices[0].message.content
            logger.debug(f"OpenAI modification response content: {content}")
            
            # JSON 추출
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            json_str = content[start_idx:end_idx]
            
            logger.debug(f"Extracted modification JSON: {json_str}")
            
            result = json.loads(json_str)
            logger.debug(f"Parsed modification JSON structure: {result}")
            return result
            
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
            response = self.azure_openai.chat.completions.create(
                model=azure_openai_deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
            )
            
            return response.choices[0].message.content
            
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
            response = self.azure_openai.chat.completions.create(
                model=azure_openai_deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
            )
            
            return response.choices[0].message.content
            
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

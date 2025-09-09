import os
import uuid
import json
from typing import Dict, Any
from openai import AzureOpenAI

try:
    from diagrams import Diagram, Cluster, Edge
    from diagrams.azure.compute import AppServices, FunctionApps, ContainerInstances, VM   
    from diagrams.azure.database import DatabaseForPostgresqlServers, CosmosDb, SQLDatabases
    from diagrams.azure.storage import StorageAccounts, BlobStorage
    from diagrams.azure.network import LoadBalancers, ApplicationGateway, CDNProfiles, VirtualNetworks
    from diagrams.azure.integration import ServiceBus, LogicApps, APIManagement
    from diagrams.azure.analytics import SynapseAnalytics, DataFactories, EventHubs
    from diagrams.azure.ml import MachineLearningServiceWorkspaces
    from diagrams.azure.security import KeyVaults, SecurityCenter
    from diagrams.azure.devops import Devops
    from diagrams.onprem.client import Users
    DIAGRAMS_AVAILABLE = True
except ImportError:
    DIAGRAMS_AVAILABLE = False

azure_openai_endpoint = os.environ.get('AZURE_OPENAI_ENDPOINT')
azure_openai_api_key = os.environ.get('AZURE_OPENAI_API_KEY')
azure_openai_deployment_name = os.environ.get('AZURE_OPENAI_DEPLOYMENT_NAME')

class ArchitectureDiagramService:
    
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
            'virtual_machines': VM,
            'postgresql': DatabaseForPostgresqlServers,
            'cosmos_db': CosmosDb,
            'sql_database': SQLDatabases,
            'storage_account': StorageAccounts,
            'blob_storage': BlobStorage,
            'load_balancer': LoadBalancers,
            'application_gateway': ApplicationGateway,
            'cdn': CDNProfiles,
            'virtual_network': VirtualNetworks,
            'api_management': APIManagement,
            'service_bus': ServiceBus,
            'event_hubs': EventHubs,
            'logic_apps': LogicApps,
            'synapse': SynapseAnalytics,
            'data_factory': DataFactories,
            'ml_workspace': MachineLearningServiceWorkspaces,
            'key_vault': KeyVaults,
            'security_center': SecurityCenter,
            'devops': Devops,
            'users': Users
        }
    
    def generate_architecture_diagram(self, requirements: str) -> Dict[str, Any]:
        """
        아키텍처 요구사항을 받아서 Azure Architecture Diagram을 생성합니다.
        
        Args:
            requirements: 자연어로 작성된 아키텍처 요구사항
            
        Returns:
            Dict containing diagram path and description
        """
        try:
            # OpenAI를 사용하여 요구사항을 분석하고 다이어그램 구조 생성
            diagram_structure = self._analyze_requirements_with_openai(requirements)
            
            # 다이어그램 생성
            diagram_path = self._create_diagram(diagram_structure)
            
            # 상세 설명 생성
            description = self._generate_description(diagram_structure, requirements)
            
            # 다이어그램과 설명을 포함한 포맷된 응답 생성
            formatted_description = self._format_description_with_diagram(description, diagram_path)
            
            return {
                'success': True,
                'diagram_path': diagram_path,
                'description': formatted_description,
                'structure': diagram_structure,
                'diagram_tag': f'<DIAGRAM>{diagram_path}</DIAGRAM>'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'diagram_path': None,
                'description': None
            }
    
    def _analyze_requirements_with_openai(self, requirements: str) -> Dict[str, Any]:
        """OpenAI를 사용하여 요구사항을 분석하고 다이어그램 구조를 생성합니다."""
        
        system_prompt = """
        당신은 Azure 아키텍처 전문가입니다. 사용자의 요구사항을 분석하여 Azure 서비스를 사용한 아키텍처 다이어그램 구조를 JSON으로 생성해주세요.

        사용 가능한 Azure 서비스들:
        - app_service: Azure App Service (웹 애플리케이션)
        - function_app: Azure Functions (서버리스 함수)
        - container_instances: Azure Container Instances
        - virtual_machines: Azure Virtual Machines
        - postgresql: Azure Database for PostgreSQL
        - cosmos_db: Azure Cosmos DB
        - sql_database: Azure SQL Database
        - storage_account: Azure Storage Account
        - blob_storage: Azure Blob Storage
        - load_balancer: Azure Load Balancer
        - application_gateway: Azure Application Gateway
        - cdn: Azure CDN
        - virtual_network: Azure Virtual Network
        - api_management: Azure API Management
        - service_bus: Azure Service Bus
        - event_hubs: Azure Event Hubs
        - logic_apps: Azure Logic Apps
        - synapse: Azure Synapse Analytics
        - data_factory: Azure Data Factory
        - ml_workspace: Azure Machine Learning
        - key_vault: Azure Key Vault
        - security_center: Azure Security Center
        - devops: Azure DevOps
        - users: Users/Clients

        JSON 응답 형식:
        {
            "title": "다이어그램 제목",
            "components": [
                {
                    "id": "component_id",
                    "service": "service_name",
                    "label": "Component Label",
                    "cluster": "cluster_name" (선택사항)
                }
            ],
            "connections": [
                {
                    "from": "component_id1",
                    "to": "component_id2",
                    "label": "connection_label" (선택사항)
                }
            ],
            "clusters": [
                {
                    "name": "cluster_name",
                    "label": "Cluster Label"
                }
            ]
        }
        """
        
        user_prompt = f"다음 아키텍처 요구사항을 분석하여 Azure 다이어그램 구조를 JSON으로 생성해주세요:\n\n{requirements}"
        
        if not self.azure_openai:
            # OpenAI가 설정되지 않은 경우 기본 구조 반환
            return self._get_default_structure()
        
        try:
            response = self.azure_openai.chat.completions.create(
                model=azure_openai_deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            
            content = response.choices[0].message.content
            # JSON 추출
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            json_str = content[start_idx:end_idx]
            
            return json.loads(json_str)
            
        except Exception as e:
            print(f"OpenAI 분석 오류: {e}")
            return self._get_default_structure()
    
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
        
        if not DIAGRAMS_AVAILABLE:
            raise ImportError("diagrams 라이브러리가 설치되지 않았습니다. 'pip install diagrams' 명령어로 설치해주세요.")
        
        # .temp 디렉토리에 다이어그램 생성
        diagram_id = str(uuid.uuid4())
        output_dir = os.path.join(os.getcwd(), '.temp')
        os.makedirs(output_dir, exist_ok=True)
        diagram_name = f"azure_architecture_{diagram_id}"
        
        with Diagram(
            structure.get('title', 'Azure Architecture'),
            filename=os.path.join(output_dir, diagram_name),
            show=False,
            direction="TB"
        ):
            # 컴포넌트 생성
            components = {}
            clusters = {}
            
            # 클러스터 생성
            for cluster_info in structure.get('clusters', []):
                cluster_name = cluster_info['name']
                cluster_label = cluster_info['label']
                clusters[cluster_name] = Cluster(cluster_label)
            
            # 컴포넌트 생성
            for component in structure.get('components', []):
                comp_id = component['id']
                service = component['service']
                label = component['label']
                cluster_name = component.get('cluster')
                
                if service in self.azure_services_map:
                    service_class = self.azure_services_map[service]
                    
                    if cluster_name and cluster_name in clusters:
                        with clusters[cluster_name]:
                            components[comp_id] = service_class(label)
                    else:
                        components[comp_id] = service_class(label)
            
            # 연결 생성
            for connection in structure.get('connections', []):
                from_comp = connection['from']
                to_comp = connection['to']
                label = connection.get('label', '')
                
                if from_comp in components and to_comp in components:
                    if label:
                        components[from_comp] >> Edge(label=label) >> components[to_comp]
                    else:
                        components[from_comp] >> components[to_comp]
        
        # 생성된 PNG 파일 경로 - 상대 경로로 반환
        png_path = f".temp/{diagram_name}.png"
        
        return png_path
    
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
                temperature=0.5
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"설명 생성 오류: {e}")
            return self._get_default_description(structure)
    
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

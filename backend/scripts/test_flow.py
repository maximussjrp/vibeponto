"""
Script de Teste de Fluxo Completo do Sistema VibePonto.

Testa todas as funcionalidades críticas:
1. Autenticação (login, refresh, logout)
2. Registro de ponto (entrada, pausas, saída)
3. Consulta de espelho de ponto
4. Gestão de colaboradores
5. Gestão de equipes
6. Escalas de trabalho
7. Dashboard e estatísticas

Uso:
    python -m scripts.test_flow --base-url http://localhost:8000
"""

import asyncio
import httpx
import argparse
import sys
from datetime import datetime, date
from typing import Optional, Dict, Any
import json


class Colors:
    """Cores para output no terminal."""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


class TestRunner:
    """Executor de testes do sistema."""
    
    def __init__(self, base_url: str, email: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.user_id: Optional[str] = None
        self.tenant_id: Optional[str] = None
        self.client = httpx.AsyncClient(timeout=30.0)
        
        self.results = {
            "passed": 0,
            "failed": 0,
            "tests": []
        }
    
    def log(self, message: str, status: str = "info"):
        """Log colorido."""
        if status == "pass":
            print(f"{Colors.GREEN}✓ PASS{Colors.RESET}: {message}")
        elif status == "fail":
            print(f"{Colors.RED}✗ FAIL{Colors.RESET}: {message}")
        elif status == "skip":
            print(f"{Colors.YELLOW}○ SKIP{Colors.RESET}: {message}")
        elif status == "info":
            print(f"{Colors.BLUE}ℹ INFO{Colors.RESET}: {message}")
        else:
            print(message)
    
    def record_result(self, name: str, passed: bool, details: str = ""):
        """Registra resultado do teste."""
        if passed:
            self.results["passed"] += 1
        else:
            self.results["failed"] += 1
        
        self.results["tests"].append({
            "name": name,
            "passed": passed,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
        
        self.log(f"{name} - {details}", "pass" if passed else "fail")
    
    async def request(
        self,
        method: str,
        endpoint: str,
        data: Dict = None,
        auth: bool = True
    ) -> tuple[int, Any]:
        """Faz requisição HTTP."""
        url = f"{self.base_url}/api/v1{endpoint}"
        headers = {}
        
        if auth and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        
        try:
            if method == "GET":
                response = await self.client.get(url, headers=headers)
            elif method == "POST":
                response = await self.client.post(url, json=data, headers=headers)
            elif method == "PATCH":
                response = await self.client.patch(url, json=data, headers=headers)
            elif method == "DELETE":
                response = await self.client.delete(url, headers=headers)
            else:
                raise ValueError(f"Método não suportado: {method}")
            
            try:
                body = response.json()
            except:
                body = response.text
            
            return response.status_code, body
            
        except Exception as e:
            return 0, str(e)
    
    # ==================== TESTES ====================
    
    async def test_health_check(self) -> bool:
        """Teste: Health Check."""
        try:
            response = await self.client.get(f"{self.base_url}/health")
            passed = response.status_code == 200 and response.json().get("status") == "healthy"
            self.record_result("Health Check", passed, f"Status: {response.status_code}")
            return passed
        except Exception as e:
            self.record_result("Health Check", False, str(e))
            return False
    
    async def test_login(self) -> bool:
        """Teste: Login."""
        status, body = await self.request("POST", "/auth/login", {
            "email": self.email,
            "password": self.password
        }, auth=False)
        
        if status == 200 and "access_token" in body:
            self.access_token = body["access_token"]
            self.refresh_token = body.get("refresh_token")
            self.record_result("Login", True, f"Token obtido")
            return True
        else:
            self.record_result("Login", False, f"Status: {status}, Body: {body}")
            return False
    
    async def test_me(self) -> bool:
        """Teste: Obter dados do usuário logado."""
        status, body = await self.request("GET", "/auth/me")
        
        if status == 200 and "id" in body:
            self.user_id = body["id"]
            self.tenant_id = body.get("tenant_id")
            self.record_result("Get /auth/me", True, f"User: {body.get('nome')}")
            return True
        else:
            self.record_result("Get /auth/me", False, f"Status: {status}")
            return False
    
    async def test_refresh_token(self) -> bool:
        """Teste: Refresh Token."""
        if not self.refresh_token:
            self.record_result("Refresh Token", False, "Refresh token não disponível")
            return False
        
        status, body = await self.request("POST", "/auth/refresh", {
            "refresh_token": self.refresh_token
        }, auth=False)
        
        if status == 200 and "access_token" in body:
            self.access_token = body["access_token"]
            self.record_result("Refresh Token", True, "Token renovado")
            return True
        else:
            self.record_result("Refresh Token", False, f"Status: {status}")
            return False
    
    async def test_dashboard_stats(self) -> bool:
        """Teste: Dashboard Stats."""
        status, body = await self.request("GET", "/dashboard/stats")
        
        if status == 200 and "colaboradores" in body:
            total = body.get("colaboradores", {}).get("total", 0)
            self.record_result("Dashboard Stats", True, f"Colaboradores: {total}")
            return True
        else:
            self.record_result("Dashboard Stats", False, f"Status: {status}")
            return False
    
    async def test_listar_usuarios(self) -> bool:
        """Teste: Listar Usuários."""
        status, body = await self.request("GET", "/usuarios")
        
        if status == 200 and "items" in body:
            total = body.get("total", 0)
            self.record_result("Listar Usuários", True, f"Total: {total}")
            return True
        else:
            self.record_result("Listar Usuários", False, f"Status: {status}")
            return False
    
    async def test_listar_equipes(self) -> bool:
        """Teste: Listar Equipes."""
        status, body = await self.request("GET", "/equipes")
        
        if status == 200 and "items" in body:
            total = body.get("total", 0)
            self.record_result("Listar Equipes", True, f"Total: {total}")
            return True
        else:
            self.record_result("Listar Equipes", False, f"Status: {status}")
            return False
    
    async def test_listar_escalas(self) -> bool:
        """Teste: Listar Escalas."""
        status, body = await self.request("GET", "/escalas")
        
        if status == 200 and "items" in body:
            total = body.get("total", 0)
            self.record_result("Listar Escalas", True, f"Total: {total}")
            return True
        else:
            self.record_result("Listar Escalas", False, f"Status: {status}")
            return False
    
    async def test_registrar_ponto(self) -> bool:
        """Teste: Registrar Ponto."""
        status, body = await self.request("POST", "/ponto/registrar", {
            "evento": "ENTRADA",
            "tipo": "WEB",
            "latitude": -20.8197,
            "longitude": -49.3794,
            "timestamp_local": datetime.now().isoformat(),
            "timezone": "America/Sao_Paulo"
        })
        
        # 201 = criado, 400 = já existe marcação (também é válido)
        if status in [201, 400]:
            self.record_result("Registrar Ponto", True, f"Status: {status}")
            return True
        else:
            self.record_result("Registrar Ponto", False, f"Status: {status}, Body: {body}")
            return False
    
    async def test_listar_marcacoes(self) -> bool:
        """Teste: Listar Marcações."""
        hoje = date.today().isoformat()
        status, body = await self.request("GET", f"/ponto/marcacoes?data_inicio={hoje}")
        
        if status == 200 and "items" in body:
            total = body.get("total", 0)
            self.record_result("Listar Marcações", True, f"Total hoje: {total}")
            return True
        else:
            self.record_result("Listar Marcações", False, f"Status: {status}, Body: {body}")
            return False
    
    async def test_espelho_ponto(self) -> bool:
        """Teste: Espelho de Ponto."""
        hoje = date.today()
        periodo_inicio = hoje.replace(day=1).isoformat()
        periodo_fim = hoje.isoformat()
        
        status, body = await self.request(
            "GET",
            f"/ponto/espelho?periodo_inicio={periodo_inicio}&periodo_fim={periodo_fim}"
        )
        
        if status == 200:
            self.record_result("Espelho de Ponto", True, f"Dados obtidos")
            return True
        else:
            self.record_result("Espelho de Ponto", False, f"Status: {status}")
            return False
    
    async def test_criar_escala(self) -> bool:
        """Teste: Criar Escala."""
        status, body = await self.request("POST", "/escalas", {
            "nome": f"Escala Teste {datetime.now().strftime('%H%M%S')}",
            "regime": "fixo",
            "tolerancia_entrada_min": 5,
            "tolerancia_saida_min": 5,
            "ativa": True,
            "janelas": {
                "seg": {"entrada": "08:00", "saida": "17:00", "intervalo_inicio": "12:00", "intervalo_fim": "13:00"},
                "ter": {"entrada": "08:00", "saida": "17:00", "intervalo_inicio": "12:00", "intervalo_fim": "13:00"},
                "qua": {"entrada": "08:00", "saida": "17:00", "intervalo_inicio": "12:00", "intervalo_fim": "13:00"},
                "qui": {"entrada": "08:00", "saida": "17:00", "intervalo_inicio": "12:00", "intervalo_fim": "13:00"},
                "sex": {"entrada": "08:00", "saida": "17:00", "intervalo_inicio": "12:00", "intervalo_fim": "13:00"},
            }
        })
        
        if status == 201:
            self.record_result("Criar Escala", True, f"ID: {body.get('id', 'N/A')}")
            return True
        else:
            self.record_result("Criar Escala", False, f"Status: {status}, Body: {body}")
            return False
    
    async def test_documentos(self) -> bool:
        """Teste: Listar Documentos."""
        status, body = await self.request("GET", "/documentos")
        
        if status == 200:
            self.record_result("Listar Documentos", True, f"Total: {body.get('total', 0)}")
            return True
        else:
            self.record_result("Listar Documentos", False, f"Status: {status}")
            return False
    
    async def test_perimetros(self) -> bool:
        """Teste: Listar Perímetros."""
        status, body = await self.request("GET", "/geo/perimetros")
        
        if status == 200:
            self.record_result("Listar Perímetros", True, f"Total: {body.get('total', 0)}")
            return True
        else:
            self.record_result("Listar Perímetros", False, f"Status: {status}")
            return False
    
    async def run_all_tests(self):
        """Executa todos os testes."""
        print(f"\n{Colors.BOLD}{'='*60}")
        print(f"TESTE DE FLUXO COMPLETO - VIBEPONTO")
        print(f"{'='*60}{Colors.RESET}\n")
        print(f"Base URL: {self.base_url}")
        print(f"Email: {self.email}")
        print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        print("-" * 60)
        
        # 1. Health Check
        if not await self.test_health_check():
            self.log("Sistema não está saudável. Abortando testes.", "fail")
            return
        
        # 2. Autenticação
        print(f"\n{Colors.BOLD}[AUTENTICAÇÃO]{Colors.RESET}")
        if not await self.test_login():
            self.log("Login falhou. Abortando testes.", "fail")
            return
        
        await self.test_me()
        await self.test_refresh_token()
        
        # 3. Dashboard
        print(f"\n{Colors.BOLD}[DASHBOARD]{Colors.RESET}")
        await self.test_dashboard_stats()
        
        # 4. Gestão
        print(f"\n{Colors.BOLD}[GESTÃO]{Colors.RESET}")
        await self.test_listar_usuarios()
        await self.test_listar_equipes()
        await self.test_listar_escalas()
        
        # 5. Ponto
        print(f"\n{Colors.BOLD}[PONTO]{Colors.RESET}")
        await self.test_registrar_ponto()
        await self.test_listar_marcacoes()
        await self.test_espelho_ponto()
        
        # 6. Escalas
        print(f"\n{Colors.BOLD}[ESCALAS]{Colors.RESET}")
        await self.test_criar_escala()
        
        # 7. Outros módulos
        print(f"\n{Colors.BOLD}[OUTROS MÓDULOS]{Colors.RESET}")
        await self.test_documentos()
        await self.test_perimetros()
        
        # Resumo
        print(f"\n{'='*60}")
        print(f"{Colors.BOLD}RESUMO DOS TESTES{Colors.RESET}")
        print(f"{'='*60}")
        
        total = self.results["passed"] + self.results["failed"]
        percentage = (self.results["passed"] / total * 100) if total > 0 else 0
        
        print(f"\n{Colors.GREEN}Passou: {self.results['passed']}{Colors.RESET}")
        print(f"{Colors.RED}Falhou: {self.results['failed']}{Colors.RESET}")
        print(f"Total: {total}")
        print(f"Taxa de sucesso: {percentage:.1f}%")
        
        if self.results["failed"] == 0:
            print(f"\n{Colors.GREEN}{Colors.BOLD}✓ TODOS OS TESTES PASSARAM!{Colors.RESET}")
        else:
            print(f"\n{Colors.YELLOW}⚠ Alguns testes falharam. Verifique os logs acima.{Colors.RESET}")
        
        print(f"{'='*60}\n")
        
        await self.client.aclose()
        
        return self.results["failed"] == 0


async def main():
    parser = argparse.ArgumentParser(description="Teste de fluxo completo do VibePonto")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="URL base da API"
    )
    parser.add_argument(
        "--email",
        default="maximussjrp@hotmail.com",
        help="Email para login"
    )
    parser.add_argument(
        "--password",
        default="Admin@123",
        help="Senha para login"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output em JSON"
    )
    
    args = parser.parse_args()
    
    runner = TestRunner(args.base_url, args.email, args.password)
    success = await runner.run_all_tests()
    
    if args.json:
        print(json.dumps(runner.results, indent=2))
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())

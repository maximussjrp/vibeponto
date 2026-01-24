"""
Serviço de Exportação AEJ - Arquivo Eletrônico de Jornada
Conforme Portaria 671/2021 do Ministério do Trabalho

Especificação: Layout AEJ versão 1.0
"""

import io
import hashlib
import logging
from datetime import datetime, date, time, timedelta, timezone
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ============== Modelos ==============

class RegistroTipo1(BaseModel):
    """Registro Tipo 1 - Cabeçalho do Arquivo"""
    tipo_registro: str = "1"
    tipo_identificador: str  # 1=CNPJ, 2=CPF
    cnpj_cpf: str  # 14 ou 11 dígitos
    cei_caepf: str = ""  # 12 dígitos
    razao_social: str  # até 150 caracteres
    data_inicial: date
    data_final: date
    data_geracao: date
    hora_geracao: time
    
    def to_line(self) -> str:
        """Gera linha formatada do registro"""
        return (
            f"{self.tipo_registro}"
            f"{self.tipo_identificador}"
            f"{self.cnpj_cpf:0>14}"
            f"{self.cei_caepf:0>12}"
            f"{self.razao_social:<150}"
            f"{self.data_inicial.strftime('%Y%m%d')}"
            f"{self.data_final.strftime('%Y%m%d')}"
            f"{self.data_geracao.strftime('%Y%m%d')}"
            f"{self.hora_geracao.strftime('%H%M%S')}"
        )


class RegistroTipo2(BaseModel):
    """Registro Tipo 2 - Identificação do Trabalhador"""
    tipo_registro: str = "2"
    pis: str  # 11 dígitos
    cpf: str  # 11 dígitos
    nome: str  # até 70 caracteres
    data_admissao: date
    cargo: str  # até 50 caracteres
    carga_horaria_semanal: int  # em minutos
    
    def to_line(self) -> str:
        return (
            f"{self.tipo_registro}"
            f"{self.pis:0>11}"
            f"{self.cpf:0>11}"
            f"{self.nome:<70}"
            f"{self.data_admissao.strftime('%Y%m%d')}"
            f"{self.cargo:<50}"
            f"{self.carga_horaria_semanal:0>4}"
        )


class RegistroTipo3(BaseModel):
    """Registro Tipo 3 - Marcações de Ponto"""
    tipo_registro: str = "3"
    pis: str  # 11 dígitos
    data: date
    hora: time
    tipo_marcacao: str  # E=Entrada, S=Saída
    tipo_registro_ponto: str  # O=Original, I=Inclusão, D=Descarte, PA=Pré-assinalado
    motivo: str = ""  # até 100 caracteres para alterações
    
    def to_line(self) -> str:
        return (
            f"{self.tipo_registro}"
            f"{self.pis:0>11}"
            f"{self.data.strftime('%Y%m%d')}"
            f"{self.hora.strftime('%H%M')}"
            f"{self.tipo_marcacao}"
            f"{self.tipo_registro_ponto:<2}"
            f"{self.motivo:<100}"
        )


class RegistroTipo4(BaseModel):
    """Registro Tipo 4 - Justificativas de Ausência"""
    tipo_registro: str = "4"
    pis: str
    data_inicio: date
    data_fim: date
    codigo_justificativa: str  # Tabela de códigos
    descricao: str  # até 100 caracteres
    
    def to_line(self) -> str:
        return (
            f"{self.tipo_registro}"
            f"{self.pis:0>11}"
            f"{self.data_inicio.strftime('%Y%m%d')}"
            f"{self.data_fim.strftime('%Y%m%d')}"
            f"{self.codigo_justificativa:0>3}"
            f"{self.descricao:<100}"
        )


class RegistroTipo5(BaseModel):
    """Registro Tipo 5 - Cálculo de Jornada Diária"""
    tipo_registro: str = "5"
    pis: str
    data: date
    horas_trabalhadas: int  # em minutos
    horas_extras_50: int  # em minutos
    horas_extras_100: int  # em minutos
    horas_noturnas: int  # em minutos
    adicional_noturno: int  # em minutos
    faltas: int  # em minutos
    atrasos: int  # em minutos
    
    def to_line(self) -> str:
        return (
            f"{self.tipo_registro}"
            f"{self.pis:0>11}"
            f"{self.data.strftime('%Y%m%d')}"
            f"{self.horas_trabalhadas:0>4}"
            f"{self.horas_extras_50:0>4}"
            f"{self.horas_extras_100:0>4}"
            f"{self.horas_noturnas:0>4}"
            f"{self.adicional_noturno:0>4}"
            f"{self.faltas:0>4}"
            f"{self.atrasos:0>4}"
        )


class RegistroTipo9(BaseModel):
    """Registro Tipo 9 - Trailer (Totalizador)"""
    tipo_registro: str = "9"
    total_registros_tipo2: int
    total_registros_tipo3: int
    total_registros_tipo4: int
    total_registros_tipo5: int
    
    def to_line(self) -> str:
        return (
            f"{self.tipo_registro}"
            f"{self.total_registros_tipo2:0>9}"
            f"{self.total_registros_tipo3:0>9}"
            f"{self.total_registros_tipo4:0>9}"
            f"{self.total_registros_tipo5:0>9}"
        )


# ============== Códigos de Justificativa ==============

CODIGOS_JUSTIFICATIVA = {
    "001": "Férias",
    "002": "Feriado",
    "003": "Folga compensação",
    "004": "Licença médica",
    "005": "Licença maternidade",
    "006": "Licença paternidade",
    "007": "Falta justificada",
    "008": "Falta injustificada",
    "009": "Abono",
    "010": "Viagem a serviço",
    "011": "Home office",
    "012": "Dispensa legal",
    "099": "Outros",
}


# ============== Serviço Principal ==============

class ExportacaoAEJService:
    """Serviço de exportação no formato AEJ - Portaria 671"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def gerar_arquivo_aej(
        self,
        tenant_id: UUID,
        data_inicial: date,
        data_final: date,
        usuario_ids: Optional[List[UUID]] = None,
    ) -> Tuple[bytes, str]:
        """
        Gera arquivo AEJ completo
        
        Returns:
            Tuple[bytes, str]: (conteúdo do arquivo, nome do arquivo)
        """
        from app.models import Tenant, Usuario, MarcacaoPonto
        
        # Buscar dados do tenant
        tenant_result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()
        
        if not tenant:
            raise ValueError("Tenant não encontrado")
        
        # Inicializar contadores
        registros_tipo2 = 0
        registros_tipo3 = 0
        registros_tipo4 = 0
        registros_tipo5 = 0
        
        linhas = []
        
        # Registro Tipo 1 - Cabeçalho
        agora = datetime.now(timezone.utc)
        tipo_id = "1" if tenant.config.get("tipo_pessoa") == "PJ" else "2"
        cnpj_cpf = tenant.config.get("cnpj") or tenant.config.get("cpf") or "00000000000000"
        
        cabecalho = RegistroTipo1(
            tipo_identificador=tipo_id,
            cnpj_cpf=cnpj_cpf.replace(".", "").replace("-", "").replace("/", ""),
            cei_caepf=tenant.config.get("cei", ""),
            razao_social=tenant.config.get("razao_social", tenant.nome),
            data_inicial=data_inicial,
            data_final=data_final,
            data_geracao=agora.date(),
            hora_geracao=agora.time(),
        )
        linhas.append(cabecalho.to_line())
        
        # Buscar usuários
        query_usuarios = select(Usuario).where(Usuario.tenant_id == tenant_id)
        if usuario_ids:
            query_usuarios = query_usuarios.where(Usuario.id.in_(usuario_ids))
        
        result_usuarios = await self.db.execute(query_usuarios)
        usuarios = result_usuarios.scalars().all()
        
        for usuario in usuarios:
            # Registro Tipo 2 - Trabalhador
            pis = (usuario.extra_data or {}).get("pis", "00000000000")
            cpf = (usuario.cpf or "00000000000").replace(".", "").replace("-", "")
            
            trabalhador = RegistroTipo2(
                pis=pis,
                cpf=cpf,
                nome=usuario.nome[:70],
                data_admissao=usuario.created_at.date(),  # Idealmente seria data_admissao
                cargo=(usuario.extra_data or {}).get("cargo", "Colaborador")[:50],
                carga_horaria_semanal=2640,  # 44h * 60min = 2640min (padrão CLT)
            )
            linhas.append(trabalhador.to_line())
            registros_tipo2 += 1
            
            # Buscar marcações do usuário no período
            result_marcacoes = await self.db.execute(
                select(MarcacaoPonto)
                .where(
                    and_(
                        MarcacaoPonto.usuario_id == usuario.id,
                        MarcacaoPonto.data_hora >= datetime.combine(data_inicial, time.min),
                        MarcacaoPonto.data_hora <= datetime.combine(data_final, time.max),
                    )
                )
                .order_by(MarcacaoPonto.data_hora)
            )
            marcacoes = result_marcacoes.scalars().all()
            
            # Agrupar marcações por dia
            marcacoes_por_dia: Dict[date, List] = {}
            for m in marcacoes:
                dia = m.data_hora.date()
                if dia not in marcacoes_por_dia:
                    marcacoes_por_dia[dia] = []
                marcacoes_por_dia[dia].append(m)
            
            # Registro Tipo 3 - Marcações
            for m in marcacoes:
                tipo_marc = "E" if m.evento in ["entrada", "pausa_fim"] else "S"
                tipo_reg = "O"  # Original
                
                if m.status == "corrigido":
                    tipo_reg = "I"  # Inclusão/Correção
                
                marcacao = RegistroTipo3(
                    pis=pis,
                    data=m.data_hora.date(),
                    hora=m.data_hora.time(),
                    tipo_marcacao=tipo_marc,
                    tipo_registro_ponto=tipo_reg,
                    motivo=m.justificativa or "",
                )
                linhas.append(marcacao.to_line())
                registros_tipo3 += 1
            
            # Registro Tipo 5 - Cálculo diário
            for dia, marcs in marcacoes_por_dia.items():
                calc = await self._calcular_jornada_dia(marcs)
                
                jornada = RegistroTipo5(
                    pis=pis,
                    data=dia,
                    horas_trabalhadas=calc["horas_trabalhadas"],
                    horas_extras_50=calc["horas_extras_50"],
                    horas_extras_100=calc["horas_extras_100"],
                    horas_noturnas=calc["horas_noturnas"],
                    adicional_noturno=calc["adicional_noturno"],
                    faltas=calc["faltas"],
                    atrasos=calc["atrasos"],
                )
                linhas.append(jornada.to_line())
                registros_tipo5 += 1
        
        # Registro Tipo 9 - Trailer
        trailer = RegistroTipo9(
            total_registros_tipo2=registros_tipo2,
            total_registros_tipo3=registros_tipo3,
            total_registros_tipo4=registros_tipo4,
            total_registros_tipo5=registros_tipo5,
        )
        linhas.append(trailer.to_line())
        
        # Gerar conteúdo
        conteudo = "\r\n".join(linhas)
        
        # Nome do arquivo
        nome_arquivo = (
            f"AEJ_{cnpj_cpf[:8]}_"
            f"{data_inicial.strftime('%Y%m%d')}_"
            f"{data_final.strftime('%Y%m%d')}.txt"
        )
        
        return conteudo.encode('utf-8'), nome_arquivo
    
    async def _calcular_jornada_dia(
        self, 
        marcacoes: List
    ) -> Dict[str, int]:
        """Calcula horas trabalhadas em um dia"""
        
        result = {
            "horas_trabalhadas": 0,
            "horas_extras_50": 0,
            "horas_extras_100": 0,
            "horas_noturnas": 0,
            "adicional_noturno": 0,
            "faltas": 0,
            "atrasos": 0,
        }
        
        if not marcacoes:
            return result
        
        # Ordenar por horário
        marcacoes_ordenadas = sorted(marcacoes, key=lambda x: x.data_hora)
        
        # Calcular tempo trabalhado
        tempo_total = timedelta()
        tempo_noturno = timedelta()
        
        i = 0
        while i < len(marcacoes_ordenadas) - 1:
            entrada = marcacoes_ordenadas[i]
            saida = marcacoes_ordenadas[i + 1] if i + 1 < len(marcacoes_ordenadas) else None
            
            if saida and entrada.evento in ["entrada", "pausa_fim"]:
                if saida.evento in ["saida", "pausa_inicio"]:
                    diff = saida.data_hora - entrada.data_hora
                    tempo_total += diff
                    
                    # Calcular tempo noturno (22h às 5h)
                    tempo_noturno += self._calcular_tempo_noturno(
                        entrada.data_hora, 
                        saida.data_hora
                    )
            
            i += 2
        
        # Converter para minutos
        minutos_trabalhados = int(tempo_total.total_seconds() / 60)
        minutos_noturnos = int(tempo_noturno.total_seconds() / 60)
        
        # Jornada padrão: 8h = 480min
        jornada_padrao = 480
        
        result["horas_trabalhadas"] = minutos_trabalhados
        result["horas_noturnas"] = minutos_noturnos
        
        # Adicional noturno (52,5% do tempo noturno convertido)
        # 1h noturna = 52min30s, então adicional = tempo_noturno * 0.1428
        result["adicional_noturno"] = int(minutos_noturnos * 0.1428)
        
        # Calcular horas extras
        if minutos_trabalhados > jornada_padrao:
            extras = minutos_trabalhados - jornada_padrao
            
            # Primeiras 2h a 50%
            if extras <= 120:
                result["horas_extras_50"] = extras
            else:
                result["horas_extras_50"] = 120
                result["horas_extras_100"] = extras - 120
        elif minutos_trabalhados < jornada_padrao:
            result["faltas"] = jornada_padrao - minutos_trabalhados
        
        return result
    
    def _calcular_tempo_noturno(
        self, 
        entrada: datetime, 
        saida: datetime
    ) -> timedelta:
        """Calcula tempo trabalhado em horário noturno (22h-5h)"""
        
        tempo_noturno = timedelta()
        
        # Definir limites do período noturno
        inicio_noite = entrada.replace(hour=22, minute=0, second=0)
        fim_noite = (entrada + timedelta(days=1)).replace(hour=5, minute=0, second=0)
        
        # Se entrada é depois das 22h
        if entrada.hour >= 22:
            inicio_periodo = entrada
            fim_periodo = min(saida, fim_noite)
            if fim_periodo > inicio_periodo:
                tempo_noturno += fim_periodo - inicio_periodo
        
        # Se saída é antes das 5h do dia seguinte
        if saida.hour < 5 or (saida.hour == 5 and saida.minute == 0):
            inicio_periodo = max(entrada, inicio_noite)
            fim_periodo = saida
            if fim_periodo > inicio_periodo:
                tempo_noturno += fim_periodo - inicio_periodo
        
        return tempo_noturno
    
    async def validar_arquivo_aej(
        self, 
        conteudo: bytes
    ) -> Dict[str, Any]:
        """Valida estrutura de arquivo AEJ"""
        
        linhas = conteudo.decode('utf-8').split('\r\n')
        
        erros = []
        avisos = []
        estatisticas = {
            "total_linhas": len(linhas),
            "registros_tipo1": 0,
            "registros_tipo2": 0,
            "registros_tipo3": 0,
            "registros_tipo4": 0,
            "registros_tipo5": 0,
            "registros_tipo9": 0,
        }
        
        for i, linha in enumerate(linhas):
            if not linha:
                continue
                
            tipo = linha[0] if linha else ""
            
            if tipo == "1":
                estatisticas["registros_tipo1"] += 1
                if i != 0:
                    erros.append(f"Linha {i+1}: Registro tipo 1 deve ser o primeiro")
            elif tipo == "2":
                estatisticas["registros_tipo2"] += 1
            elif tipo == "3":
                estatisticas["registros_tipo3"] += 1
            elif tipo == "4":
                estatisticas["registros_tipo4"] += 1
            elif tipo == "5":
                estatisticas["registros_tipo5"] += 1
            elif tipo == "9":
                estatisticas["registros_tipo9"] += 1
                if i != len(linhas) - 1:
                    avisos.append(f"Linha {i+1}: Registro tipo 9 deve ser o último")
            else:
                erros.append(f"Linha {i+1}: Tipo de registro inválido '{tipo}'")
        
        # Validar contadores do trailer
        if estatisticas["registros_tipo9"] == 1:
            ultima_linha = linhas[-1]
            if len(ultima_linha) >= 37:
                try:
                    t2_declarado = int(ultima_linha[1:10])
                    t3_declarado = int(ultima_linha[10:19])
                    t4_declarado = int(ultima_linha[19:28])
                    t5_declarado = int(ultima_linha[28:37])
                    
                    if t2_declarado != estatisticas["registros_tipo2"]:
                        erros.append(f"Contador tipo 2 incorreto: {t2_declarado} != {estatisticas['registros_tipo2']}")
                    if t3_declarado != estatisticas["registros_tipo3"]:
                        erros.append(f"Contador tipo 3 incorreto: {t3_declarado} != {estatisticas['registros_tipo3']}")
                    if t4_declarado != estatisticas["registros_tipo4"]:
                        erros.append(f"Contador tipo 4 incorreto: {t4_declarado} != {estatisticas['registros_tipo4']}")
                    if t5_declarado != estatisticas["registros_tipo5"]:
                        erros.append(f"Contador tipo 5 incorreto: {t5_declarado} != {estatisticas['registros_tipo5']}")
                except:
                    erros.append("Erro ao ler contadores do trailer")
        
        return {
            "valido": len(erros) == 0,
            "erros": erros,
            "avisos": avisos,
            "estatisticas": estatisticas,
        }


class ExportacaoAFDService:
    """
    Serviço de exportação AFD - Arquivo de Fonte de Dados
    Para REPs (Registradores Eletrônicos de Ponto)
    """
    
    async def gerar_arquivo_afd(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        data_inicial: date,
        data_final: date,
        numero_rep: str = "000000000000000001",
    ) -> Tuple[bytes, str]:
        """Gera arquivo AFD conforme Portaria 1510/2009"""
        from app.models import Usuario, MarcacaoPonto
        
        linhas = []
        nsr = 1  # Número Sequencial do Registro
        
        # Registro tipo 1 - Cabeçalho (não usado em todos os REPs)
        
        # Buscar marcações
        result = await db.execute(
            select(MarcacaoPonto, Usuario)
            .join(Usuario, MarcacaoPonto.usuario_id == Usuario.id)
            .where(
                and_(
                    MarcacaoPonto.tenant_id == tenant_id,
                    MarcacaoPonto.data_hora >= datetime.combine(data_inicial, time.min),
                    MarcacaoPonto.data_hora <= datetime.combine(data_final, time.max),
                )
            )
            .order_by(MarcacaoPonto.data_hora)
        )
        
        for marcacao, usuario in result.all():
            pis = (usuario.extra_data or {}).get("pis", "00000000000")
            
            # Formato AFD tipo 3 (marcação de ponto)
            linha = (
                f"{nsr:09d}"  # NSR
                f"3"  # Tipo de registro
                f"{marcacao.data_hora.strftime('%d%m%Y')}"  # Data
                f"{marcacao.data_hora.strftime('%H%M')}"  # Hora
                f"{pis:0>11}"  # PIS
            )
            linhas.append(linha)
            nsr += 1
        
        conteudo = "\r\n".join(linhas)
        nome_arquivo = f"AFD_{numero_rep}_{data_inicial.strftime('%Y%m%d')}_{data_final.strftime('%Y%m%d')}.txt"
        
        return conteudo.encode('utf-8'), nome_arquivo

"""Serviço de geração de PDF para espelhos e comprovantes."""

from datetime import datetime
from io import BytesIO
from typing import Any
import base64

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.core.config import settings


class PDFService:
    """Serviço de geração de PDFs."""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_styles()
    
    def _setup_styles(self) -> None:
        """Configura estilos customizados."""
        self.styles.add(ParagraphStyle(
            name="Title-Custom",
            parent=self.styles["Title"],
            fontSize=18,
            textColor=colors.HexColor("#1a56db"),
            spaceAfter=20,
        ))
        self.styles.add(ParagraphStyle(
            name="Subtitle-Custom",
            parent=self.styles["Heading2"],
            fontSize=12,
            textColor=colors.HexColor("#4b5563"),
            spaceAfter=10,
        ))
        self.styles.add(ParagraphStyle(
            name="Normal-Small",
            parent=self.styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#6b7280"),
        ))
    
    def gerar_comprovante_marcacao(
        self,
        usuario_nome: str,
        usuario_matricula: str,
        empresa_nome: str,
        evento: str,
        timestamp: datetime,
        comprovante_hash: str,
        latitude: float | None = None,
        longitude: float | None = None,
        foto_base64: str | None = None,
    ) -> bytes:
        """
        Gera PDF de comprovante de marcação.
        
        Conforme Portaria 671 do MTE.
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )
        
        elements = []
        
        # Cabeçalho
        elements.append(Paragraph(
            f"🕐 {settings.app_name}",
            self.styles["Title-Custom"],
        ))
        elements.append(Paragraph(
            f"COMPROVANTE DE MARCAÇÃO DE PONTO",
            self.styles["Heading2"],
        ))
        elements.append(Spacer(1, 20))
        
        # Linha divisória
        elements.append(Table(
            [[""]],
            colWidths=[16 * cm],
            style=TableStyle([
                ("LINEBELOW", (0, 0), (-1, -1), 2, colors.HexColor("#1a56db")),
            ]),
        ))
        elements.append(Spacer(1, 20))
        
        # Dados da empresa
        elements.append(Paragraph(
            f"<b>Empresa:</b> {empresa_nome}",
            self.styles["Normal"],
        ))
        elements.append(Spacer(1, 10))
        
        # Dados do colaborador
        data_table = [
            ["Colaborador:", usuario_nome],
            ["Matrícula:", usuario_matricula],
            ["Tipo de Marcação:", evento.upper()],
            ["Data:", timestamp.strftime("%d/%m/%Y")],
            ["Hora:", timestamp.strftime("%H:%M:%S")],
        ]
        
        if latitude and longitude:
            data_table.append(["Localização:", f"{latitude:.6f}, {longitude:.6f}"])
        
        table = Table(
            data_table,
            colWidths=[5 * cm, 11 * cm],
            style=TableStyle([
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                ("ALIGN", (1, 0), (1, -1), "LEFT"),
            ]),
        )
        elements.append(table)
        elements.append(Spacer(1, 30))
        
        # Foto (se disponível)
        if foto_base64:
            try:
                foto_data = base64.b64decode(foto_base64)
                foto_io = BytesIO(foto_data)
                img = Image(foto_io, width=4 * cm, height=4 * cm)
                elements.append(Paragraph("<b>Foto da Marcação:</b>", self.styles["Normal"]))
                elements.append(Spacer(1, 10))
                elements.append(img)
                elements.append(Spacer(1, 20))
            except Exception:
                pass
        
        # Hash de verificação
        elements.append(Paragraph(
            "<b>Código de Autenticação:</b>",
            self.styles["Normal"],
        ))
        elements.append(Paragraph(
            f"<font name='Courier' size='8'>{comprovante_hash}</font>",
            self.styles["Normal"],
        ))
        elements.append(Spacer(1, 20))
        
        # Aviso legal
        elements.append(Paragraph(
            "─" * 80,
            self.styles["Normal-Small"],
        ))
        elements.append(Paragraph(
            "Este documento é um comprovante oficial de marcação de ponto eletrônico, "
            "emitido em conformidade com a Portaria 671 do Ministério do Trabalho e Emprego. "
            f"Documento gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}.",
            self.styles["Normal-Small"],
        ))
        
        doc.build(elements)
        return buffer.getvalue()
    
    def gerar_espelho_ponto(
        self,
        usuario_nome: str,
        usuario_matricula: str,
        usuario_cpf: str,
        empresa_nome: str,
        empresa_cnpj: str,
        periodo_inicio: datetime,
        periodo_fim: datetime,
        dias: list[dict[str, Any]],
        totais: dict[str, Any],
        assinaturas: list[dict[str, Any]] | None = None,
    ) -> bytes:
        """
        Gera PDF do espelho de ponto mensal.
        
        Conforme Portaria 671 do MTE.
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=1.5 * cm,
            leftMargin=1.5 * cm,
            topMargin=1.5 * cm,
            bottomMargin=2 * cm,
        )
        
        elements = []
        
        # Cabeçalho
        header_data = [
            [
                Paragraph(f"<b>{settings.app_name}</b>", self.styles["Normal"]),
                Paragraph("<b>ESPELHO DE PONTO ELETRÔNICO</b>", self.styles["Normal"]),
                Paragraph(
                    f"Período: {periodo_inicio.strftime('%d/%m/%Y')} a {periodo_fim.strftime('%d/%m/%Y')}",
                    self.styles["Normal"],
                ),
            ],
        ]
        header_table = Table(
            header_data,
            colWidths=[5.5 * cm, 7 * cm, 5.5 * cm],
            style=TableStyle([
                ("ALIGN", (0, 0), (0, 0), "LEFT"),
                ("ALIGN", (1, 0), (1, 0), "CENTER"),
                ("ALIGN", (2, 0), (2, 0), "RIGHT"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]),
        )
        elements.append(header_table)
        elements.append(Spacer(1, 15))
        
        # Dados da empresa e colaborador
        info_data = [
            [
                Paragraph(f"<b>Empresa:</b> {empresa_nome}", self.styles["Normal"]),
                Paragraph(f"<b>CNPJ:</b> {empresa_cnpj}", self.styles["Normal"]),
            ],
            [
                Paragraph(f"<b>Colaborador:</b> {usuario_nome}", self.styles["Normal"]),
                Paragraph(f"<b>Matrícula:</b> {usuario_matricula}", self.styles["Normal"]),
            ],
            [
                Paragraph(f"<b>CPF:</b> {usuario_cpf}", self.styles["Normal"]),
                "",
            ],
        ]
        info_table = Table(
            info_data,
            colWidths=[10 * cm, 8 * cm],
            style=TableStyle([
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]),
        )
        elements.append(info_table)
        elements.append(Spacer(1, 15))
        
        # Tabela de marcações
        header_row = ["Data", "Entrada", "Saída Alm.", "Volta Alm.", "Saída", "Trabalhado", "Obs"]
        table_data = [header_row]
        
        for dia in dias:
            data = dia.get("data", "")
            marcacoes = dia.get("marcacoes", [])
            
            # Extrair horários das marcações
            entrada = ""
            saida_almoco = ""
            volta_almoco = ""
            saida = ""
            
            for m in marcacoes:
                evento = m.get("evento", "")
                hora = m.get("hora", "")
                
                if evento == "entrada":
                    entrada = hora
                elif evento == "pausa_inicio":
                    saida_almoco = hora
                elif evento == "pausa_fim":
                    volta_almoco = hora
                elif evento == "saida":
                    saida = hora
            
            horas = dia.get("horas_trabalhadas", "-")
            obs = ", ".join(dia.get("observacoes", []))[:20]
            
            table_data.append([
                data if isinstance(data, str) else data.strftime("%d/%m"),
                entrada,
                saida_almoco,
                volta_almoco,
                saida,
                horas,
                obs,
            ])
        
        marcacoes_table = Table(
            table_data,
            colWidths=[2.2 * cm, 2 * cm, 2.2 * cm, 2.2 * cm, 2 * cm, 2.4 * cm, 3.5 * cm],
            style=TableStyle([
                # Header
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a56db")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                # Body
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("ALIGN", (0, 1), (-1, -1), "CENTER"),
                # Grid
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
                # Padding
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]),
        )
        elements.append(marcacoes_table)
        elements.append(Spacer(1, 20))
        
        # Totais
        totais_data = [
            ["RESUMO DO PERÍODO"],
            [
                f"Dias Trabalhados: {totais.get('dias', 0)}",
                f"Horas Trabalhadas: {totais.get('horas', '00:00')}",
                f"Horas Extras: {totais.get('extras', '00:00')}",
            ],
            [
                f"Atrasos: {totais.get('atrasos', 0)}",
                f"Faltas: {totais.get('faltas', 0)}",
                f"Banco de Horas: {totais.get('banco', '00:00')}",
            ],
        ]
        totais_table = Table(
            totais_data,
            colWidths=[6 * cm, 6 * cm, 6 * cm],
            style=TableStyle([
                ("SPAN", (0, 0), (-1, 0)),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]),
        )
        elements.append(totais_table)
        elements.append(Spacer(1, 30))
        
        # Área de assinaturas
        elements.append(Paragraph("<b>ASSINATURAS:</b>", self.styles["Normal"]))
        elements.append(Spacer(1, 15))
        
        assinatura_data = [
            ["_" * 40, "_" * 40],
            ["Colaborador", "Responsável RH/DP"],
            ["", ""],
            ["Data: ___/___/_____", "Data: ___/___/_____"],
        ]
        
        if assinaturas:
            for ass in assinaturas:
                assinatura_data.append([
                    f"✓ Assinado digitalmente por: {ass.get('nome', '')}",
                    f"em {ass.get('data', '')}",
                ])
        
        assinatura_table = Table(
            assinatura_data,
            colWidths=[9 * cm, 9 * cm],
            style=TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
            ]),
        )
        elements.append(assinatura_table)
        elements.append(Spacer(1, 20))
        
        # Rodapé legal
        elements.append(Paragraph(
            "─" * 100,
            self.styles["Normal-Small"],
        ))
        elements.append(Paragraph(
            "Documento emitido em conformidade com a Portaria 671/MTE. "
            "A veracidade das informações contidas neste espelho pode ser verificada "
            "através do código de autenticação no rodapé de cada página. "
            f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}",
            self.styles["Normal-Small"],
        ))
        
        doc.build(elements)
        return buffer.getvalue()
    
    def gerar_aej_pdf(
        self,
        empresa_nome: str,
        empresa_cnpj: str,
        periodo_inicio: datetime,
        periodo_fim: datetime,
        registros: list[dict[str, Any]],
        hash_arquivo: str,
    ) -> bytes:
        """
        Gera versão PDF do AEJ para conferência visual.
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=1.5 * cm,
            leftMargin=1.5 * cm,
            topMargin=1.5 * cm,
            bottomMargin=2 * cm,
        )
        
        elements = []
        
        # Título
        elements.append(Paragraph(
            "ARQUIVO ELETRÔNICO DE JORNADA (AEJ)",
            self.styles["Title-Custom"],
        ))
        elements.append(Paragraph(
            "Portaria 671/MTE - Relatório de Conferência",
            self.styles["Subtitle-Custom"],
        ))
        elements.append(Spacer(1, 20))
        
        # Dados do arquivo
        info = [
            ["Empresa:", empresa_nome],
            ["CNPJ:", empresa_cnpj],
            ["Período:", f"{periodo_inicio.strftime('%d/%m/%Y')} a {periodo_fim.strftime('%d/%m/%Y')}"],
            ["Total de Registros:", str(len(registros))],
            ["Hash SHA-256:", hash_arquivo[:32] + "..."],
        ]
        info_table = Table(
            info,
            colWidths=[4 * cm, 14 * cm],
            style=TableStyle([
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]),
        )
        elements.append(info_table)
        elements.append(Spacer(1, 20))
        
        # Primeiros N registros como amostra
        header = ["CPF", "Matrícula", "Data", "Hora", "Evento", "Tipo"]
        table_data = [header]
        
        for reg in registros[:50]:  # Limitar a 50 para não ficar muito grande
            table_data.append([
                reg.get("cpf", ""),
                reg.get("matricula", ""),
                reg.get("data", ""),
                reg.get("hora", ""),
                reg.get("evento", ""),
                reg.get("tipo", ""),
            ])
        
        if len(registros) > 50:
            table_data.append(["...", "...", "...", "...", "...", "..."])
        
        reg_table = Table(
            table_data,
            colWidths=[3 * cm, 2.5 * cm, 2.5 * cm, 2 * cm, 3 * cm, 3 * cm],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a56db")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]),
        )
        elements.append(reg_table)
        elements.append(Spacer(1, 20))
        
        # Aviso
        elements.append(Paragraph(
            "<b>ATENÇÃO:</b> Este é um relatório de conferência visual. "
            "O arquivo oficial AEJ em formato texto (.txt) deve ser utilizado "
            "para transmissão ao MTE ou arquivamento legal.",
            self.styles["Normal-Small"],
        ))
        
        doc.build(elements)
        return buffer.getvalue()


# Singleton
pdf_service = PDFService()

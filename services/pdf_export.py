from io import BytesIO
from pathlib import Path

from reportlab.lib import utils
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer


def _fit_image(path: Path, max_width: int = 220, max_height: int = 160):
    img_reader = utils.ImageReader(str(path))
    img_width, img_height = img_reader.getSize()

    ratio = min(max_width / img_width, max_height / img_height)
    width = img_width * ratio
    height = img_height * ratio

    return Image(str(path), width=width, height=height)


def build_aps_pdf(aps, uploads_dir: Path) -> BytesIO:
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        name="TitleCenter",
        parent=styles["Title"],
        alignment=TA_CENTER,
    )

    center_style = ParagraphStyle(
        name="Center",
        parent=styles["Normal"],
        alignment=TA_CENTER,
    )

    heading_center_style = ParagraphStyle(
        name="HeadingCenter",
        parent=styles["Heading3"],
        alignment=TA_CENTER,
    )

    elements = []

    elements.append(Paragraph("AP Manager - Relatório de Access Points", title_style))
    elements.append(Spacer(1, 18))

    if not aps:
        elements.append(Paragraph("Não existem APs registados.", center_style))
    else:
        for idx, ap in enumerate(aps, start=1):
            elements.append(Paragraph(f"<b>Registo {idx}</b>", heading_center_style))
            elements.append(Paragraph(f"<b>Quarto:</b> {ap.quarto}", center_style))
            elements.append(Paragraph(f"<b>MAC:</b> {ap.mac}", center_style))

            if getattr(ap, "data_registo", None):
                elements.append(
                    Paragraph(
                        f"<b>Data de registo:</b> {ap.data_registo.strftime('%d/%m/%Y %H:%M')}",
                        center_style,
                    )
                )

            foto_path = getattr(ap, "foto_path", None)
            if foto_path:
                full_path = uploads_dir / foto_path
                if full_path.exists() and full_path.is_file():
                    try:
                        elements.append(Spacer(1, 8))
                        img = _fit_image(full_path)
                        img.hAlign = "CENTER"
                        elements.append(img)
                    except Exception:
                        elements.append(
                            Paragraph(
                                "Imagem disponível, mas não foi possível inseri-la no PDF.",
                                center_style,
                            )
                        )
                else:
                    elements.append(Paragraph("Imagem não encontrada no servidor.", center_style))
            else:
                elements.append(Paragraph("Sem imagem associada.", center_style))

            elements.append(Spacer(1, 20))

    doc.build(elements)
    buffer.seek(0)
    return buffer
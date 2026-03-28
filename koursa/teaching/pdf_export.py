import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT


def generate_fiche_pdf(fiche):
    """
    Genere un PDF reproduisant la fiche de suivi des enseignements
    a partir d'un objet FicheSuivi.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()
    elements = []

    # ── Styles personnalises ──
    style_header_fr = ParagraphStyle(
        'HeaderFR', parent=styles['Normal'],
        fontSize=8, leading=10, alignment=TA_CENTER,
    )
    style_header_en = ParagraphStyle(
        'HeaderEN', parent=styles['Normal'],
        fontSize=8, leading=10, alignment=TA_CENTER,
    )
    style_header_bold = ParagraphStyle(
        'HeaderBold', parent=styles['Normal'],
        fontSize=8, leading=10, alignment=TA_CENTER, fontName='Helvetica-Bold',
    )
    style_title = ParagraphStyle(
        'FicheTitle', parent=styles['Normal'],
        fontSize=14, leading=18, alignment=TA_CENTER,
        fontName='Helvetica-Bold', spaceAfter=6 * mm,
    )
    style_label = ParagraphStyle(
        'Label', parent=styles['Normal'],
        fontSize=10, leading=13, fontName='Helvetica-Bold',
    )
    style_value = ParagraphStyle(
        'Value', parent=styles['Normal'],
        fontSize=10, leading=13,
    )
    style_section_title = ParagraphStyle(
        'SectionTitle', parent=styles['Normal'],
        fontSize=12, leading=15, alignment=TA_CENTER,
        fontName='Helvetica-Bold', spaceBefore=4 * mm, spaceAfter=2 * mm,
    )
    style_content = ParagraphStyle(
        'Content', parent=styles['Normal'],
        fontSize=10, leading=14,
    )
    style_signature = ParagraphStyle(
        'Signature', parent=styles['Normal'],
        fontSize=10, leading=13, fontName='Helvetica-Bold',
    )

    # ── Extraire les infos de la fiche ──
    # Departement / Faculte depuis l'UE -> niveaux -> filiere -> departement -> faculte
    departement_nom = ""
    faculte_nom = ""
    niveaux = fiche.ue.niveaux.select_related('filiere__departement__faculte').all() if fiche.ue else []
    if niveaux:
        niveau = niveaux[0]
        filiere = niveau.filiere
        if filiere and filiere.departement:
            departement_nom = filiere.departement.nom_departement
            if filiere.departement.faculte:
                faculte_nom = filiere.departement.faculte.nom_faculte

    # ── EN-TETE BILINGUE ──
    header_fr = (
        f"REPUBLIQUE DU CAMEROUN<br/>"
        f"<i>Paix - Travail - Patrie</i><br/>"
        f"*****<br/>"
        f"<b>UNIVERSITE DE YAOUNDE I</b><br/>"
        f"<b>{faculte_nom or 'Faculte des Sciences'}</b><br/>"
        f"<i>Departement d'{departement_nom or 'Informatique'}</i><br/>"
        f"B.P. 812 Yaounde"
    )
    header_en = (
        f"REPUBLIC OF CAMEROON<br/>"
        f"<i>Peace - Work - Fatherland</i><br/>"
        f"*****<br/>"
        f"<b>UNIVERSITY OF YAOUNDE I</b><br/>"
        f"<b>{faculte_nom or 'Faculty of Science'}</b><br/>"
        f"<i>Department of {departement_nom or 'Computer Science'}</i><br/>"
        f"P.O.Box 812 Yaounde"
    )

    page_width = A4[0] - 3 * cm  # largeur utilisable
    header_table = Table(
        [[Paragraph(header_fr, style_header_fr), Paragraph(header_en, style_header_en)]],
        colWidths=[page_width / 2, page_width / 2],
    )
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 8 * mm))

    # ── TITRE ──
    elements.append(Paragraph("FICHE DE SUIVI DES ENSEIGNEMENTS", style_title))

    # ── GRILLE D'INFORMATIONS ──
    # Calculer les valeurs
    semestre_val = ""
    if fiche.semestre:
        semestre_val = f"Semestre {fiche.semestre.numero}"
    elif fiche.ue and fiche.ue.semestre:
        semestre_val = f"Semestre {fiche.ue.semestre}"

    ue_val = ""
    if fiche.ue:
        ue_val = f"{fiche.ue.code_ue} - {fiche.ue.libelle_ue}"

    enseignant_val = ""
    if fiche.enseignant:
        enseignant_val = f"{fiche.enseignant.first_name} {fiche.enseignant.last_name}"

    salle_val = ""
    if fiche.salle:
        salle_val = fiche.salle.nom_salle

    date_val = ""
    if fiche.date_cours:
        date_val = fiche.date_cours.strftime("%d/%m/%Y")

    heure_debut_val = fiche.heure_debut.strftime("%H:%M") if fiche.heure_debut else ""
    heure_fin_val = fiche.heure_fin.strftime("%H:%M") if fiche.heure_fin else ""

    total_horaire = ""
    if fiche.duree:
        total_seconds = int(fiche.duree.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        total_horaire = f"{hours}h{minutes:02d}"

    type_seance_val = fiche.type_seance or ""

    def make_cell(label, value):
        return [
            Paragraph(f"<b>{label}</b>", style_label),
            Paragraph(str(value), style_value),
        ]

    col_width = page_width / 2
    half = col_width - 2 * mm

    info_data = [
        [
            Paragraph(f"<b>Semestre:</b> {semestre_val}", style_label),
            Paragraph(f"<b>Date:</b> {date_val}", style_label),
        ],
        [
            Paragraph(f"<b>UE:</b> {ue_val}", style_label),
            Paragraph(f"<b>Heure du debut:</b> {heure_debut_val}", style_label),
        ],
        [
            Paragraph(f"<b>Enseignant:</b> {enseignant_val}", style_label),
            Paragraph(f"<b>Heure de la fin:</b> {heure_fin_val}", style_label),
        ],
        [
            Paragraph(f"<b>Salle:</b> {salle_val}", style_label),
            Paragraph(f"<b>Total horaire:</b> {total_horaire}", style_label),
        ],
        [
            Paragraph(f"<b>Seance de (CM/TP/TD):</b> {type_seance_val}", style_label),
            "",
        ],
        [
            Paragraph(f"<b>Titre:</b> {fiche.titre_chapitre or ''}", style_label),
            "",
        ],
    ]

    info_table = Table(info_data, colWidths=[col_width, col_width])
    info_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        # Merge les lignes Seance et Titre sur toute la largeur
        ('SPAN', (0, 4), (1, 4)),
        ('SPAN', (0, 5), (1, 5)),
    ]))
    elements.append(info_table)

    # ── CONTENU ──
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph("<b>Contenu</b>", style_section_title))

    contenu_text = fiche.contenu_aborde or ""
    # Remplacer les retours a la ligne par des <br/>
    contenu_text = contenu_text.replace('\n', '<br/>')

    content_data = [[Paragraph(contenu_text, style_content)]]
    content_table = Table(content_data, colWidths=[page_width])
    content_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('MINROWHEIGHT', (0, 0), (-1, -1), 12 * cm),
    ]))
    elements.append(content_table)

    # ── SIGNATURES ──
    elements.append(Spacer(1, 10 * mm))

    delegue_nom = ""
    if fiche.delegue:
        delegue_nom = f"{fiche.delegue.first_name} {fiche.delegue.last_name}"

    sig_data = [
        [
            Paragraph("Signature du delegue", style_signature),
            Paragraph("Signature de l'enseignant", style_signature),
        ],
        [
            Paragraph(f"<i>{delegue_nom}</i>", style_value),
            Paragraph(f"<i>{enseignant_val}</i>", style_value),
        ],
    ]
    sig_table = Table(sig_data, colWidths=[col_width, col_width])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(sig_table)

    # ── GENERATION ──
    doc.build(elements)
    buffer.seek(0)
    return buffer

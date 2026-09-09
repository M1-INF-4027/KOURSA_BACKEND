"""
Socle commun aux imports Excel de la plateforme.

Regroupe la normalisation des en-tetes, la deduction du niveau depuis un code
UE et le format de rapport renvoye par tous les endpoints d'import. Ces regles
etaient jusqu'ici dupliquees cote navigateur (UEsPage.jsx) ; elles font
desormais autorite ici.
"""
import re
import unicodedata


# ---------------------------------------------------------------------------
# Normalisation des en-tetes
# ---------------------------------------------------------------------------

# Chaque cle canonique regroupe les intitules de colonnes acceptes.
# Portage fidele de normalizeHeader() de KOURSA_FONTEND_WEB/src/pages/admin/UEsPage.jsx
HEADER_ALIASES = {
    'code': ['code', 'code_ue', 'codes_2025_2026', 'code_ue_intitule'],
    'libelle': ['libelle', 'libelle_ue', 'intitule', 'intitule_ue'],
    'semestre': ['semestre', 'semestre_obj', 'sem'],
    'niveau': ['niveau', 'niveaux'],
    'enseignant': ['enseignant', 'enseignant_nom', 'nom_enseignant'],
    'enseignant_email': ['enseignant_email', 'email_enseignant'],
    'email': ['email', 'adresse_email', 'mail'],
    'role': ['role', 'role_type', 'type_role'],
    'nom_complet': ['nom_complet', 'nom', 'nom_et_prenom'],
    'nom_salle': ['nom_salle', 'salle', 'nom_de_salle'],
    'faculte': ['faculte', 'nom_faculte'],
    'departement': ['departement', 'nom_departement'],
    'filiere': ['filiere', 'nom_filiere'],
}

# Index inverse alias -> cle canonique, construit une fois.
_ALIAS_INDEX = {
    alias: canonical
    for canonical, aliases in HEADER_ALIASES.items()
    for alias in aliases
}


def strip_accents(value):
    """Retire les accents : 'libellé' -> 'libelle'."""
    normalized = unicodedata.normalize('NFD', str(value))
    return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')


def normalize_header(header):
    """
    Ramene un intitule de colonne a sa cle canonique.

    'Code UE' -> 'code', 'Libellé' -> 'libelle', 'Nom complet' -> 'nom_complet'.
    Un intitule inconnu est renvoye normalise (minuscules, underscores), ce qui
    permet aux appelants de lire des colonnes supplementaires sans les declarer.
    """
    key = strip_accents(header).strip().lower()
    key = re.sub(r'[\s_-]+', '_', key)
    return _ALIAS_INDEX.get(key, key)


# ---------------------------------------------------------------------------
# Deduction du niveau depuis le code UE
# ---------------------------------------------------------------------------

# 1 -> L1, 2 -> L2, 3 -> L3, 4 -> M1, 5 -> M2
NIVEAU_PAR_CHIFFRE = {1: 'L1', 2: 'L2', 3: 'L3', 4: 'M1', 5: 'M2'}


def detect_niveau_from_code(code):
    """
    Deduit le nom du niveau du premier chiffre suivant les lettres du code.

    INF3xx -> 'L3', ICT4xx -> 'M1'. Renvoie None si le code ne suit pas ce
    motif. Portage fidele de detectNiveauFromCode() cote navigateur.
    """
    if not code:
        return None
    match = re.match(r'^[A-Za-z]+(\d)', str(code).strip())
    if not match:
        return None
    return NIVEAU_PAR_CHIFFRE.get(int(match.group(1)))


# ---------------------------------------------------------------------------
# Lecture des classeurs
# ---------------------------------------------------------------------------

class ExcelInvalide(Exception):
    """Fichier illisible ou vide."""


def read_sheet(file, required=None):
    """
    Lit la premiere feuille d'un classeur et renvoie une liste de (ligne, dict).

    Les en-tetes sont normalises via normalize_header(). Le numero de ligne est
    celui du tableur (en-tete = 1), afin que les erreurs renvoyees soient
    directement exploitables par l'utilisateur.

    `required` liste les cles canoniques devant etre presentes ; leur absence
    leve ExcelInvalide plutot que de produire un import silencieusement vide.
    """
    import openpyxl

    try:
        wb = openpyxl.load_workbook(file, read_only=True, data_only=True)
        ws = wb.active
    except Exception:
        raise ExcelInvalide('Fichier Excel invalide ou illisible.')

    rows = ws.iter_rows(values_only=True)
    try:
        header_row = next(rows)
    except StopIteration:
        raise ExcelInvalide('Le fichier est vide.')

    headers = [normalize_header(h) if h is not None else '' for h in header_row]

    if required:
        manquantes = [c for c in required if c not in headers]
        if manquantes:
            raise ExcelInvalide(
                'Colonnes manquantes : {}. Colonnes trouvees : {}.'.format(
                    ', '.join(manquantes),
                    ', '.join(h for h in headers if h) or 'aucune',
                )
            )

    result = []
    for line_no, row in enumerate(rows, start=2):
        values = {}
        for header, cell in zip(headers, row):
            if not header:
                continue
            values[header] = '' if cell is None else str(cell).strip()
        # Ignore les lignes entierement vides, frequentes en fin de tableur.
        if any(values.values()):
            result.append((line_no, values))

    wb.close()
    return result


# ---------------------------------------------------------------------------
# Rapport d'import
# ---------------------------------------------------------------------------

class ImportReport:
    """
    Accumule le resultat d'un import pour renvoyer une reponse homogene.

    Tous les endpoints d'import repondent avec la meme forme, ce qui permet au
    composant ImportPanel cote navigateur de les traiter indifferemment.
    """

    def __init__(self):
        self.created = 0
        self.updated = 0
        self.skipped = 0
        self.errors = []

    def error(self, line, message):
        self.errors.append({'ligne': line, 'message': str(message)})

    def as_dict(self):
        return {
            'created': self.created,
            'updated': self.updated,
            'skipped': self.skipped,
            'errors': self.errors,
            'total': self.created + self.updated + self.skipped + len(self.errors),
        }


# ---------------------------------------------------------------------------
# Import en deux temps : simulation puis validation
# ---------------------------------------------------------------------------

# Statuts d'une ligne simulee.
STATUT_OK = 'ok'                      # prete a etre ecrite
STATUT_PARENT_ABSENT = 'parent_absent'  # le parent nomme n'existe pas encore
STATUT_DOUBLON = 'doublon'            # deja presente en base
STATUT_ERREUR = 'erreur'              # ligne inexploitable


class PreviewReport:
    """
    Resultat d'une simulation d'import.

    Symetrique d'ImportReport : la simulation decrit ce qui *serait* ecrit,
    l'ecriture rapporte ce qui l'a ete. Le navigateur consomme les deux avec le
    meme composant.
    """

    def __init__(self):
        self.lignes = []

    def ajouter(self, ligne, valeurs, parent=None, statut=STATUT_OK, message=None):
        """
        `parent` decrit le rattachement propose :
            {'champ': 'departement', 'id': 3 ou None, 'libelle': 'Informatique'}
        Un id nul avec un libelle renseigne signale un parent a arbitrer.
        """
        self.lignes.append({
            'ligne': ligne,
            'valeurs': valeurs,
            'parent': parent,
            'statut': statut,
            'message': message,
        })

    def as_dict(self):
        compte = {}
        for l in self.lignes:
            compte[l['statut']] = compte.get(l['statut'], 0) + 1
        return {
            'lignes': self.lignes,
            'resume': compte,
            'total': len(self.lignes),
        }


def est_simulation(request):
    """Vrai si l'appel demande une simulation plutot qu'une ecriture."""
    valeur = request.data.get('dry_run') or request.query_params.get('dry_run')
    return str(valeur).lower() in ('1', 'true', 'oui', 'yes')


def parse_rows(request, required=None):
    """
    Retourne les lignes a traiter, quelle que soit la forme de l'appel.

    Deux entrees possibles :
      - un fichier Excel (`file`), lors de la simulation initiale ;
      - un tableau JSON `rows`, lors de la validation, apres arbitrage de
        l'administrateur dans l'apercu.

    Dans les deux cas le format de sortie est identique — [(numero, dict)] —
    de sorte que les endpoints n'ont pas a se dedoubler.

    Leve ExcelInvalide si aucune entree exploitable n'est fournie.
    """
    fichier = request.FILES.get('file')
    if fichier is not None:
        return read_sheet(fichier, required=required)

    rows = request.data.get('rows')
    if isinstance(rows, str):
        import json
        try:
            rows = json.loads(rows)
        except ValueError:
            raise ExcelInvalide("Le champ 'rows' n'est pas un JSON valide.")

    if not rows:
        raise ExcelInvalide("Aucun fichier ni aucune ligne fournie.")
    if not isinstance(rows, list):
        raise ExcelInvalide("Le champ 'rows' doit etre une liste.")

    resultat = []
    for i, brut in enumerate(rows, start=2):
        if not isinstance(brut, dict):
            continue
        # Le numero de ligne d'origine est conserve pour que les messages
        # d'erreur restent comprehensibles apres edition dans l'apercu.
        numero = brut.get('ligne', i)
        valeurs = brut.get('valeurs', brut)
        valeurs = {k: ('' if v is None else str(v).strip()) for k, v in valeurs.items()}
        # Champs de pilotage transmis par l'apercu.
        for cle in ('parent_id', 'creer_parent', 'parent_libelle'):
            if cle in brut:
                valeurs[cle] = brut[cle]
        resultat.append((numero, valeurs))
    return resultat

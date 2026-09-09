import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.views import APIView
from django.db import transaction
from common.import_utils import (
    STATUT_DOUBLON,
    STATUT_OK,
    STATUT_PARENT_ABSENT,
    ExcelInvalide,
    ImportReport,
    PreviewReport,
    est_simulation,
    parse_rows,
    read_sheet,
    strip_accents,
)
from users.permissions import IsSuperAdmin
from users.models import Role

logger = logging.getLogger('koursa')
from .models import Faculte, Departement, Filiere, Niveau, AnneeAcademique, Semestre, HistoriqueChefDepartement, Salle
from .serializers import (
    FaculteSerializer, DepartementSerializer, FiliereSerializer, NiveauSerializer,
    AnneeAcademiqueSerializer, SemestreSerializer, HistoriqueChefSerializer,
    SalleSerializer,
)

class FaculteViewSet(viewsets.ModelViewSet):
    queryset = Faculte.objects.all()
    serializer_class = FaculteSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsSuperAdmin]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['post'], url_path='import',
            parser_classes=[MultiPartParser, FormParser, JSONParser],
            permission_classes=[IsSuperAdmin])
    def import_facultes(self, request):
        """Importer des facultes. Colonne : `faculte`."""
        return importer_hierarchique(
            request, Faculte, 'nom_faculte', 'faculte',
        )


class DepartementViewSet(viewsets.ModelViewSet):
    queryset = Departement.objects.select_related('faculte', 'chef_departement').all()
    serializer_class = DepartementSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsSuperAdmin]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['post'], url_path='import',
            parser_classes=[MultiPartParser, FormParser, JSONParser],
            permission_classes=[IsSuperAdmin])
    def import_departements(self, request):
        """Importer des departements. Colonnes : `departement`, `faculte`."""
        return importer_hierarchique(
            request, Departement, 'nom_departement', 'departement',
            parent={'champ': 'faculte', 'modele': Faculte,
                    'champ_nom': 'nom_faculte', 'colonne': 'faculte'},
        )

    def _sync_chef_role(self, old_chef, new_chef):
        """Ajoute/retire le role Chef de Departement automatiquement."""
        chef_role = Role.objects.filter(nom_role=Role.CHEF_DEPARTEMENT).first()
        if not chef_role:
            return

        # Retirer le role de l'ancien chef s'il ne gere plus aucun departement
        if old_chef and old_chef != new_chef:
            still_chef = Departement.objects.filter(chef_departement=old_chef).exists()
            if not still_chef:
                old_chef.roles.remove(chef_role)

        # Ajouter le role au nouveau chef
        if new_chef and new_chef != old_chef:
            new_chef.roles.add(chef_role)
            new_chef.statut = 'ACTIF'
            new_chef.save(update_fields=['statut'])

    def perform_create(self, serializer):
        instance = serializer.save()
        self._sync_chef_role(None, instance.chef_departement)

    def perform_update(self, serializer):
        old_chef = self.get_object().chef_departement
        instance = serializer.save()
        self._sync_chef_role(old_chef, instance.chef_departement)

class FiliereViewSet(viewsets.ModelViewSet):
    queryset = Filiere.objects.select_related('departement', 'departement__faculte').all()
    serializer_class = FiliereSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsSuperAdmin]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['post'], url_path='import',
            parser_classes=[MultiPartParser, FormParser, JSONParser],
            permission_classes=[IsSuperAdmin])
    def import_filieres(self, request):
        """Importer des filieres. Colonnes : `filiere`, `departement`."""
        return importer_hierarchique(
            request, Filiere, 'nom_filiere', 'filiere',
            parent={'champ': 'departement', 'modele': Departement,
                    'champ_nom': 'nom_departement', 'colonne': 'departement',
                    'parent_requis': {'champ': 'faculte', 'modele': Faculte}},
        )

class NiveauViewSet(viewsets.ModelViewSet):
    queryset = Niveau.objects.select_related('filiere').all()
    serializer_class = NiveauSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsSuperAdmin]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['post'], url_path='import',
            parser_classes=[MultiPartParser, FormParser, JSONParser],
            permission_classes=[IsSuperAdmin])
    def import_niveaux(self, request):
        """Importer des niveaux. Colonnes : `niveau`, `filiere`."""
        return importer_hierarchique(
            request, Niveau, 'nom_niveau', 'niveau',
            parent={'champ': 'filiere', 'modele': Filiere,
                    'champ_nom': 'nom_filiere', 'colonne': 'filiere',
                    'parent_requis': {'champ': 'departement', 'modele': Departement}},
        )

    def get_queryset(self):
        qs = super().get_queryset()
        departement_id = self.request.query_params.get('departement')
        if departement_id:
            qs = qs.filter(filiere__departement_id=departement_id)
        return qs


class SalleViewSet(viewsets.ModelViewSet):
    queryset = Salle.objects.all()
    serializer_class = SalleSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsSuperAdmin]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['delete'], url_path='delete-all')
    def delete_all(self, request):
        """Supprimer toutes les salles."""
        count = Salle.objects.count()
        Salle.objects.all().delete()
        logger.warning(f'Toutes les salles supprimees ({count}) par {request.user.email}')
        return Response({'deleted': count}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='import',
            parser_classes=[MultiPartParser, FormParser, JSONParser],
            permission_classes=[IsSuperAdmin])
    def import_salles(self, request):
        """Importer des salles. Colonne : `nom_salle`. Aucun rattachement."""
        return importer_hierarchique(
            request, Salle, 'nom_salle', 'nom_salle',
        )


class AnneeAcademiqueViewSet(viewsets.ModelViewSet):
    queryset = AnneeAcademique.objects.prefetch_related('semestres').all()
    serializer_class = AnneeAcademiqueSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsSuperAdmin()]


class SemestreViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Semestre.objects.select_related('annee_academique').all()
    serializer_class = SemestreSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['annee_academique', 'est_actif']


class HistoriqueChefViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = HistoriqueChefDepartement.objects.select_related(
        'departement', 'utilisateur', 'annee_academique'
    ).all()
    serializer_class = HistoriqueChefSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['departement', 'annee_academique']

class StructureImportView(APIView):
    """
    POST /api/academic/structure/import/

    Importe la hierarchie academique complete depuis un fichier Excel :
    Faculte -> Departement -> Filiere -> Niveau, une ligne par niveau.

    Colonnes reconnues : `faculte`, `departement`, `filiere`, `niveau`.
    Chaque niveau de la hierarchie est cree s'il n'existe pas, ce qui rend le
    fichier rejouable et permet de le completer par la suite.
    """
    permission_classes = [IsSuperAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'detail': 'Aucun fichier fourni.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            rows = read_sheet(file, required=['faculte', 'departement', 'filiere'])
        except ExcelInvalide as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        report = ImportReport()

        with transaction.atomic():
            for line, values in rows:
                nom_faculte = (values.get('faculte') or '').strip()
                nom_departement = (values.get('departement') or '').strip()
                nom_filiere = (values.get('filiere') or '').strip()
                nom_niveau = (values.get('niveau') or '').strip().upper()

                if not (nom_faculte and nom_departement and nom_filiere):
                    report.error(
                        line,
                        'Les colonnes faculte, departement et filiere doivent etre renseignees.',
                    )
                    continue

                faculte, _ = Faculte.objects.get_or_create(nom_faculte=nom_faculte)
                departement, _ = Departement.objects.get_or_create(
                    nom_departement=nom_departement, faculte=faculte
                )
                filiere, _ = Filiere.objects.get_or_create(
                    nom_filiere=nom_filiere, departement=departement
                )

                # La colonne niveau est facultative : une ligne sans niveau cree
                # seulement la branche faculte / departement / filiere.
                if not nom_niveau:
                    report.skipped += 1
                    continue

                _, cree = Niveau.objects.get_or_create(
                    nom_niveau=nom_niveau, filiere=filiere
                )
                if cree:
                    report.created += 1
                else:
                    report.skipped += 1

        logger.info(
            f'Import structure par {request.user.email}: '
            f'{report.created} niveaux crees, {report.skipped} deja presents'
        )
        return Response(report.as_dict(), status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Import hierarchique generique
# ---------------------------------------------------------------------------

def importer_hierarchique(request, modele, champ_nom, colonne, parent=None):
    """
    Import d'une entite de la hierarchie academique, en simulation ou en ecriture.

    Les quatre echelons (faculte, departement, filiere, niveau) ne different que
    par leur modele, leur champ de nom et leur parent : une seule mecanique les
    couvre donc tous.

    `parent`, quand il existe :
        {'champ': 'departement',        # nom du champ sur le modele
         'modele': Departement,
         'champ_nom': 'nom_departement',
         'colonne': 'departement'}      # colonne du fichier portant son nom

    Le parent est resolu dans cet ordre :
      1. `parent_id` transmis par l'apercu — l'administrateur a tranche ;
      2. correspondance sur le nom lu dans le fichier ;
      3. `creer_parent` : creation explicitement autorisee dans l'apercu.
    Sans resolution, la ligne est signalee `parent_absent` et n'est jamais ecrite.
    """
    try:
        lignes = parse_rows(request, required=[colonne])
    except ExcelInvalide as e:
        return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    simulation = est_simulation(request)

    # Index des parents existants, par nom normalise.
    index_parents = {}
    if parent:
        for obj in parent['modele'].objects.all():
            index_parents[strip_accents(getattr(obj, parent['champ_nom'])).strip().lower()] = obj

    # Parent impose a toutes les lignes (choix global dans l'apercu).
    parent_global = None
    if parent:
        brut = request.data.get(parent['champ'])
        if brut:
            parent_global = parent['modele'].objects.filter(pk=brut).first()

    apercu = PreviewReport()
    rapport = ImportReport()
    deja_vus = set()

    with transaction.atomic():
        for numero, valeurs in lignes:
            nom = (valeurs.get(colonne) or '').strip()
            if not nom:
                continue

            # --- resolution du parent ---------------------------------------
            objet_parent = None
            libelle_parent = ''
            if parent:
                libelle_parent = (valeurs.get(parent['colonne']) or '').strip()

                parent_id = valeurs.get('parent_id')
                if parent_id:
                    objet_parent = parent['modele'].objects.filter(pk=parent_id).first()
                elif libelle_parent:
                    objet_parent = index_parents.get(
                        strip_accents(libelle_parent).strip().lower()
                    )
                elif parent_global:
                    objet_parent = parent_global

                if objet_parent is None and valeurs.get('creer_parent') and libelle_parent:
                    # Le parent a creer peut lui-meme exiger un rattachement
                    # (un departement appartient a une faculte). On ne peut le
                    # deviner que s'il n'existe qu'un seul candidat.
                    champs_parent = {parent['champ_nom']: libelle_parent}
                    aieul_requis = parent.get('parent_requis')
                    refus = None
                    if aieul_requis:
                        candidats = list(aieul_requis['modele'].objects.all()[:2])
                        if len(candidats) == 1:
                            champs_parent[aieul_requis['champ']] = candidats[0]
                        elif not candidats:
                            refus = (
                                f"Impossible de creer {libelle_parent} : aucun "
                                f"{aieul_requis['champ']} n'existe encore."
                            )
                        else:
                            refus = (
                                f"Impossible de creer {libelle_parent} automatiquement : "
                                f"plusieurs {aieul_requis['champ']}s existent, "
                                f"choisissez un {parent['champ']} existant."
                            )

                    if refus:
                        if simulation:
                            apercu.ajouter(
                                numero, {champ_nom: nom},
                                parent={'champ': parent['champ'], 'id': None, 'libelle': libelle_parent},
                                statut=STATUT_PARENT_ABSENT, message=refus,
                            )
                        else:
                            rapport.error(numero, refus)
                        continue

                    if simulation:
                        # On n'ecrit rien : la ligne est annoncee comme creable.
                        apercu.ajouter(
                            numero, {champ_nom: nom},
                            parent={'champ': parent['champ'], 'id': None, 'libelle': libelle_parent},
                            statut=STATUT_OK,
                            message=f"{libelle_parent} sera cree",
                        )
                        continue

                    objet_parent = parent['modele'].objects.create(**champs_parent)
                    index_parents[strip_accents(libelle_parent).strip().lower()] = objet_parent

                if objet_parent is None:
                    message = (
                        f"Parent introuvable : {libelle_parent}"
                        if libelle_parent else "Aucun parent indique"
                    )
                    if simulation:
                        apercu.ajouter(
                            numero, {champ_nom: nom},
                            parent={'champ': parent['champ'], 'id': None, 'libelle': libelle_parent},
                            statut=STATUT_PARENT_ABSENT, message=message,
                        )
                    else:
                        rapport.error(numero, message)
                    continue

            # --- doublons ---------------------------------------------------
            criteres = {champ_nom: nom}
            if parent and objet_parent:
                criteres[parent['champ']] = objet_parent

            cle = (nom.lower(), objet_parent.pk if objet_parent else None)
            existe = modele.objects.filter(**criteres).exists() or cle in deja_vus
            deja_vus.add(cle)

            if simulation:
                apercu.ajouter(
                    numero, {champ_nom: nom},
                    parent=(
                        {'champ': parent['champ'],
                         'id': objet_parent.pk if objet_parent else None,
                         'libelle': getattr(objet_parent, parent['champ_nom']) if objet_parent else libelle_parent}
                        if parent else None
                    ),
                    statut=STATUT_DOUBLON if existe else STATUT_OK,
                    message="Deja presente" if existe else None,
                )
                continue

            _, cree = modele.objects.get_or_create(**criteres)
            if cree:
                rapport.created += 1
            else:
                rapport.skipped += 1

        if simulation:
            # Aucune ecriture ne doit subsister d'une simulation.
            transaction.set_rollback(True)
            return Response(apercu.as_dict(), status=status.HTTP_200_OK)

    logger.info(
        f'Import {modele.__name__} par {request.user.email}: '
        f'{rapport.created} crees, {rapport.skipped} existants'
    )
    return Response(rapport.as_dict(), status=status.HTTP_200_OK)

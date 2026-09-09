from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from users.permissions import IsSuperAdmin, IsHoD
from django.db import transaction
from datetime import date

from .models import (
    AnneeAcademique, Semestre, Departement, Filiere, Niveau,
    Faculte, HistoriqueChefDepartement, Salle,
)
from .serializers import (
    AnneeAcademiqueSerializer,
    SemestreSerializer,
    CreateAnneeAcademiqueSerializer,
)


# Etapes qu'une annee doit reellement satisfaire pour etre consideree configuree.
# Les enseignants et les chefs de departement en sont volontairement exclus :
# ils sont recommandes, mais une annee peut demarrer avant que tous soient nommes.
ETAPES_OBLIGATOIRES = [
    ('annee_creee', "l'annee academique"),
    ('semestres_configures', 'les deux semestres'),
    ('facultes_creees', 'au moins une faculte'),
    ('departements_crees', 'au moins un departement'),
    ('filieres_creees', 'au moins une filiere'),
    ('niveaux_crees', 'au moins un niveau'),
    ('salles_creees', 'au moins une salle'),
    ('ues_creees', "au moins une unite d'enseignement"),
]


def construire_checklist(annee):
    """
    Etat reel de la configuration d'une annee, deduit des donnees en base.

    Source unique de verite, partagee par la vue de statut, la checklist du
    wizard et le marquage manuel : ces trois points de vue ne peuvent donc plus
    diverger.
    """
    from teaching.models import UniteEnseignement
    from users.models import Role, Utilisateur

    if annee is None:
        return {
            'annee_creee': False,
            'semestres_configures': False,
            'facultes_creees': False,
            'departements_crees': False,
            'filieres_creees': False,
            'niveaux_crees': False,
            'salles_creees': False,
            'enseignants_crees': False,
            'ues_creees': False,
            'ues_sans_enseignant': 0,
            'departements_sans_chef': Departement.objects.count(),
        }

    ues_annee = UniteEnseignement.objects.filter(semestre_obj__annee_academique=annee)
    return {
        'annee_creee': True,
        'semestres_configures': annee.semestres.count() == 2,
        'facultes_creees': Faculte.objects.exists(),
        'departements_crees': Departement.objects.exists(),
        'filieres_creees': Filiere.objects.exists(),
        'niveaux_crees': Niveau.objects.exists(),
        'salles_creees': Salle.objects.filter(est_active=True).exists(),
        'enseignants_crees': Utilisateur.objects.filter(roles__nom_role=Role.ENSEIGNANT).exists(),
        'ues_creees': ues_annee.exists(),
        'ues_sans_enseignant': ues_annee.filter(enseignants__isnull=True).count(),
        'departements_sans_chef': Departement.objects.filter(chef_departement__isnull=True).count(),
    }


def etapes_manquantes(checklist):
    """Libelles des etapes obligatoires non satisfaites."""
    return [libelle for cle, libelle in ETAPES_OBLIGATOIRES if not checklist.get(cle)]


def annee_est_configuree(annee):
    """
    Une annee n'est configuree que si l'administrateur l'a declaree *et* que les
    donnees suivent. Le drapeau seul avait permis de verrouiller la plateforme
    sur une annee vide, sans moyen de reprendre le wizard.
    """
    if annee is None or not annee.est_configuree:
        return False
    return not etapes_manquantes(construire_checklist(annee))


class ConfigurationStatusView(APIView):
    """GET /api/configuration/status/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        annee_active = AnneeAcademique.objects.filter(est_active=True).first()
        semestre_actif = Semestre.objects.filter(est_actif=True).select_related('annee_academique').first()

        return Response({
            'est_configure': annee_est_configuree(annee_active),
            'annee_active': AnneeAcademiqueSerializer(annee_active).data if annee_active else None,
            'semestre_actif': SemestreSerializer(semestre_actif).data if semestre_actif else None,
            'toutes_annees': AnneeAcademiqueSerializer(
                AnneeAcademique.objects.prefetch_related('semestres').all(), many=True
            ).data,
        })


class CreateAnneeAcademiqueView(APIView):
    """POST /api/configuration/annee-academique/"""
    permission_classes = [IsSuperAdmin]

    def post(self, request):
        serializer = CreateAnneeAcademiqueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        with transaction.atomic():
            annee = AnneeAcademique.objects.create(
                libelle=d['libelle'],
                est_active=True,
                est_configuree=False,
            )
            Semestre.objects.create(
                annee_academique=annee, numero=1,
                date_debut=d['s1_date_debut'], date_fin=d['s1_date_fin'],
                est_actif=True,
            )
            Semestre.objects.create(
                annee_academique=annee, numero=2,
                date_debut=d['s2_date_debut'], date_fin=d['s2_date_fin'],
                est_actif=False,
            )

        annee.refresh_from_db()
        return Response(
            AnneeAcademiqueSerializer(annee).data,
            status=status.HTTP_201_CREATED
        )


class ActivateAnneeView(APIView):
    """POST /api/configuration/annee-academique/{id}/activer/"""
    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        try:
            annee = AnneeAcademique.objects.get(pk=pk)
        except AnneeAcademique.DoesNotExist:
            return Response({'detail': 'Annee non trouvee.'}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            annee.est_active = True
            annee.save()
            # Activer le S1 de cette annee (desactive les autres semestres via Semestre.save())
            s1 = Semestre.objects.filter(annee_academique=annee, numero=1).first()
            if s1:
                s1.est_actif = True
                s1.save()

        return Response(AnneeAcademiqueSerializer(annee).data)


class ActivateSemestreView(APIView):
    """POST /api/configuration/semestre/{id}/activer/"""
    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        try:
            semestre = Semestre.objects.select_related('annee_academique').get(pk=pk)
        except Semestre.DoesNotExist:
            return Response({'detail': 'Semestre non trouve.'}, status=status.HTTP_404_NOT_FOUND)
        semestre.est_actif = True
        semestre.save()
        # Aussi activer l'annee parente si pas deja active
        if not semestre.annee_academique.est_active:
            semestre.annee_academique.est_active = True
            semestre.annee_academique.save()
        return Response(SemestreSerializer(semestre).data)


class ReconduireAnneeView(APIView):
    """POST /api/configuration/annee-academique/{id}/reconduire/"""
    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        from teaching.models import UniteEnseignement

        try:
            new_annee = AnneeAcademique.objects.prefetch_related('semestres').get(pk=pk)
        except AnneeAcademique.DoesNotExist:
            return Response({'detail': 'Annee non trouvee.'}, status=status.HTTP_404_NOT_FOUND)

        previous = AnneeAcademique.objects.prefetch_related('semestres').exclude(pk=pk).order_by('-libelle').first()
        if not previous:
            return Response({'detail': "Pas d'annee precedente."}, status=status.HTTP_400_BAD_REQUEST)

        prev_semestres = {s.numero: s for s in previous.semestres.all()}
        new_semestres = {s.numero: s for s in new_annee.semestres.all()}

        created_count = 0
        with transaction.atomic():
            for num, prev_sem in prev_semestres.items():
                new_sem = new_semestres.get(num)
                if not new_sem:
                    continue

                prev_ues = UniteEnseignement.objects.filter(
                    semestre_obj=prev_sem
                ).prefetch_related('enseignants', 'niveaux')

                for prev_ue in prev_ues:
                    # Verifier si l'UE existe deja pour ce semestre
                    if UniteEnseignement.objects.filter(code_ue=prev_ue.code_ue, semestre_obj=new_sem).exists():
                        continue

                    new_ue = UniteEnseignement.objects.create(
                        code_ue=prev_ue.code_ue,
                        libelle_ue=prev_ue.libelle_ue,
                        semestre=num,
                        semestre_obj=new_sem,
                    )
                    new_ue.enseignants.set(prev_ue.enseignants.all())
                    new_ue.niveaux.set(prev_ue.niveaux.all())
                    created_count += 1

            # Reconduire les chefs
            for dept in Departement.objects.filter(chef_departement__isnull=False):
                HistoriqueChefDepartement.objects.get_or_create(
                    departement=dept,
                    utilisateur_id=dept.chef_departement_id,
                    annee_academique=new_annee,
                    defaults={'date_debut': date.today()}
                )

        return Response({
            'detail': f'Reconduction effectuee. {created_count} UEs copiees.',
            'ues_copiees': created_count,
        })


class MarkConfiguredView(APIView):
    """POST /api/configuration/annee-academique/{id}/marquer-configuree/"""
    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        try:
            annee = AnneeAcademique.objects.get(pk=pk)
        except AnneeAcademique.DoesNotExist:
            return Response({'detail': 'Annee non trouvee.'}, status=status.HTTP_404_NOT_FOUND)
        manquantes = etapes_manquantes(construire_checklist(annee))
        if manquantes:
            return Response(
                {
                    'detail': "Configuration incomplete : " + ", ".join(manquantes) + ".",
                    'etapes_manquantes': manquantes,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        annee.est_configuree = True
        annee.save()
        return Response(AnneeAcademiqueSerializer(annee).data)


class SetupChecklistView(APIView):
    """GET /api/configuration/checklist/"""
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        annee = AnneeAcademique.objects.filter(est_active=True).first()
        checklist = construire_checklist(annee)
        manquantes = etapes_manquantes(checklist)

        return Response({
            'annee': AnneeAcademiqueSerializer(annee).data if annee else None,
            'checklist': checklist,
            'etapes_manquantes': manquantes,
            'est_configuree': annee_est_configuree(annee),
        })


class ChefChecklistView(APIView):
    """GET /api/configuration/chef-checklist/"""
    permission_classes = [IsAuthenticated, IsHoD]

    def get(self, request):
        from teaching.models import UniteEnseignement

        try:
            departement = Departement.objects.get(chef_departement=request.user)
        except Departement.DoesNotExist:
            return Response({'detail': 'Non assigne a un departement.'}, status=status.HTTP_404_NOT_FOUND)

        filieres = Filiere.objects.filter(departement=departement)
        niveaux = Niveau.objects.filter(filiere__departement=departement)
        ues = UniteEnseignement.objects.filter(niveaux__filiere__departement=departement).distinct()
        ues_sans_enseignant = ues.filter(enseignants__isnull=True).count()
        delegues_en_attente = Utilisateur.objects.filter(
            niveau_represente__filiere__departement=departement,
            statut='EN_ATTENTE'
        ).count()

        return Response({
            'departement': departement.nom_departement,
            'filieres_ok': filieres.exists(),
            'niveaux_ok': niveaux.exists(),
            'nb_filieres': filieres.count(),
            'nb_niveaux': niveaux.count(),
            'nb_ues': ues.count(),
            'ues_sans_enseignant': ues_sans_enseignant,
            'delegues_en_attente': delegues_en_attente,
        })


# Import Utilisateur here to avoid circular import at module level
from users.models import Utilisateur

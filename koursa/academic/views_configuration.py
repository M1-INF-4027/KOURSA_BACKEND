from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from users.permissions import IsSuperAdmin, IsHoD
from django.db import transaction
from datetime import date

from .models import (
    AnneeAcademique, Semestre, Departement, Filiere, Niveau,
    Faculte, HistoriqueChefDepartement,
)
from .serializers import (
    AnneeAcademiqueSerializer,
    SemestreSerializer,
    CreateAnneeAcademiqueSerializer,
)


class ConfigurationStatusView(APIView):
    """GET /api/configuration/status/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        annee_active = AnneeAcademique.objects.filter(est_active=True).first()
        semestre_actif = Semestre.objects.filter(est_actif=True).select_related('annee_academique').first()

        return Response({
            'est_configure': annee_active is not None and annee_active.est_configuree,
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
        annee.est_active = True
        annee.save()
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
        annee.est_configuree = True
        annee.save()
        return Response(AnneeAcademiqueSerializer(annee).data)


class SetupChecklistView(APIView):
    """GET /api/configuration/checklist/"""
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        from teaching.models import UniteEnseignement

        annee = AnneeAcademique.objects.filter(est_active=True).first()
        if not annee:
            return Response({
                'annee': None,
                'checklist': {
                    'annee_creee': False,
                    'semestres_configures': False,
                    'facultes_creees': False,
                    'departements_crees': False,
                    'filieres_creees': False,
                    'niveaux_crees': False,
                    'ues_creees': False,
                    'ues_sans_enseignant': 0,
                    'departements_sans_chef': Departement.objects.count(),
                },
                'est_configuree': False,
            })

        semestres = annee.semestres.all()
        ues_in_year = UniteEnseignement.objects.filter(semestre_obj__annee_academique=annee)

        return Response({
            'annee': AnneeAcademiqueSerializer(annee).data,
            'checklist': {
                'annee_creee': True,
                'semestres_configures': semestres.count() == 2,
                'facultes_creees': Faculte.objects.exists(),
                'departements_crees': Departement.objects.exists(),
                'filieres_creees': Filiere.objects.exists(),
                'niveaux_crees': Niveau.objects.exists(),
                'ues_creees': ues_in_year.exists(),
                'ues_sans_enseignant': ues_in_year.filter(enseignants__isnull=True).count(),
                'departements_sans_chef': Departement.objects.filter(chef_departement__isnull=True).count(),
            },
            'est_configuree': annee.est_configuree,
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

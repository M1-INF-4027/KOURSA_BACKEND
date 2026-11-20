import logging
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.throttling import AnonRateThrottle
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.conf import settings
from django.db import transaction
from common.import_utils import (
    STATUT_DOUBLON,
    STATUT_ERREUR,
    STATUT_OK,
    ExcelInvalide,
    ImportReport,
    PreviewReport,
    est_simulation,
    parse_rows,
    read_sheet,
)
import firebase_admin
from firebase_admin import auth as firebase_auth
from .models import Utilisateur, Role, StatutCompte, AuthProvider, EmailWhitelist
from .permissions import IsHoD, IsSuperAdmin, IsHoDOrSuperAdmin, IsAdminOrIsSelf
from datetime import timedelta
from .serializers import UtilisateurSerializer, RoleSerializer, PasswordConfirmationSerializer, ChangePasswordSerializer, MyTokenObtainPairSerializer, EmailWhitelistSerializer
from django.db.models.functions import Lower
from teaching.models import UniteEnseignement
from academic.models import Departement
from notifications.services import create_and_send_notification
from notifications.models import NotificationType

logger = logging.getLogger('koursa')

class UtilisateurViewSet(viewsets.ModelViewSet):
    # Les champs `classe` et `enseignements` du serializer traversent le niveau,
    # la filiere, le departement et les UEs : sans ces jointures, afficher la
    # liste des utilisateurs declencherait une requete par ligne.
    queryset = Utilisateur.objects.all().prefetch_related(
        'roles', 'ues_enseignees__niveaux'
    ).select_related(
        'niveau_represente__filiere__departement'
    )
    serializer_class = UtilisateurSerializer
    permission_classes = [IsAdminOrIsSelf]

    filterset_fields = ['roles', 'statut']

    def get_queryset(self):
        user = self.request.user
        
        if not user.is_authenticated:
            return Utilisateur.objects.none()
            
        if user.roles.filter(nom_role=Role.SUPER_ADMIN).exists():
            return self.queryset
        
        if user.roles.filter(nom_role=Role.CHEF_DEPARTEMENT).exists() and user.departement_gere:
            departement = user.departement_gere
            delegues_ids = Utilisateur.objects.filter(niveau_represente__filiere__departement=departement).values_list('id', flat=True)
            # Enseignants qui ont des UEs dans les niveaux du departement
            enseignants_avec_ues = Utilisateur.objects.filter(
                roles__nom_role=Role.ENSEIGNANT,
                ues_enseignees__niveaux__filiere__departement=departement
            ).values_list('id', flat=True)
            # Enseignants whitelistes dans ce departement (pas encore d'UEs assignees)
            whitelisted_emails = list(
                EmailWhitelist.objects.filter(
                    departement=departement, role_type='ENSEIGNANT'
                ).values_list('email', flat=True)
            )
            whitelisted_emails_lower = [e.lower() for e in whitelisted_emails]
            enseignants_whitelistes = Utilisateur.objects.filter(
                roles__nom_role=Role.ENSEIGNANT,
            ).annotate(
                email_lower=Lower('email')
            ).filter(
                email_lower__in=whitelisted_emails_lower
            ).values_list('id', flat=True)
            all_ids = set(list(delegues_ids) + list(enseignants_avec_ues) + list(enseignants_whitelistes)) | {user.id}
            return self.queryset.filter(id__in=list(all_ids))
        
        
        return self.queryset.filter(pk=user.pk)

    def perform_destroy(self, instance):
        user = self.request.user
        # Un Chef de Département ne peut supprimer que des délégués de son département
        if user.roles.filter(nom_role=Role.CHEF_DEPARTEMENT).exists():
            if not instance.roles.filter(nom_role=Role.DELEGUE).exists():
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Vous ne pouvez supprimer que des délégués.")
            # Vérifier que le délégué appartient au département du chef
            if hasattr(user, 'departement_gere') and user.departement_gere:
                if instance.niveau_represente and instance.niveau_represente.filiere.departement != user.departement_gere:
                    raise PermissionDenied("Ce délégué n'appartient pas à votre département.")
        instance.delete()

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated], url_path='confirm-password')
    def confirm_password(self, request):
        user = request.user
        serializer = PasswordConfirmationSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        password = serializer.validated_data['password']
        
        if not user.check_password(password):
            return Response({"detail": "Mot de passe incorrect."}, status=status.HTTP_403_FORBIDDEN)
        
        validation_token = AccessToken.for_user(user)
        validation_token.set_exp(lifetime=timedelta(minutes=20)) 
        
        validation_token['token_class'] = 'validation'
        
        return Response({
            'validation_token': str(validation_token)
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated], url_path='approuver')
    def approuver(self, request, pk=None):
        """Approuver un utilisateur en attente (délégué ou enseignant)"""
        approbateur = request.user

        # Un compte qui n'est pas lui-meme actif n'approuve personne. Le
        # controle de role ci-dessous ne lit pas `statut`, et rien d'autre ne
        # le faisait sur ce chemin : un chef encore en attente de validation
        # pouvait donc valider les comptes des autres.
        if approbateur.statut != StatutCompte.ACTIF and not approbateur.is_superuser:
            return Response({"detail": "Votre compte n'est pas actif."},
                            status=status.HTTP_403_FORBIDDEN)

        # Seuls le Super Admin et le Chef de Département peuvent approuver
        is_super_admin = approbateur.roles.filter(nom_role=Role.SUPER_ADMIN).exists() or approbateur.is_superuser
        is_hod = approbateur.roles.filter(nom_role=Role.CHEF_DEPARTEMENT).exists()

        if not is_super_admin and not is_hod:
            return Response({"detail": "Vous n'avez pas la permission d'approuver des utilisateurs."}, status=status.HTTP_403_FORBIDDEN)

        utilisateur = self.get_object()

        # Vérifier que l'utilisateur est en attente
        if utilisateur.statut != StatutCompte.EN_ATTENTE:
            return Response({"detail": "Cet utilisateur n'est pas en attente de validation."}, status=status.HTTP_400_BAD_REQUEST)

        is_delegue = utilisateur.roles.filter(nom_role=Role.DELEGUE).exists()
        is_enseignant = utilisateur.roles.filter(nom_role=Role.ENSEIGNANT).exists()

        # Le Chef de Département ne peut approuver que les délégués et enseignants
        if is_hod and not is_super_admin and not is_delegue and not is_enseignant:
            return Response({"detail": "Seuls les délégués et enseignants peuvent être approuvés."}, status=status.HTTP_400_BAD_REQUEST)

        # Vérifications spécifiques au Chef de Département
        if is_hod and not is_super_admin:
            if not hasattr(approbateur, 'departement_gere') or not approbateur.departement_gere:
                return Response({"detail": "Vous n'êtes assigné à aucun département."}, status=status.HTTP_403_FORBIDDEN)

            # Pour un délégué, vérifier qu'il appartient au département du chef
            if is_delegue:
                if not utilisateur.niveau_represente:
                    return Response({"detail": "Ce délégué n'a pas de niveau représenté assigné."}, status=status.HTTP_400_BAD_REQUEST)
                if utilisateur.niveau_represente.filiere.departement != approbateur.departement_gere:
                    return Response({"detail": "Cet utilisateur n'appartient pas à votre département."}, status=status.HTTP_403_FORBIDDEN)

        utilisateur.statut = StatutCompte.ACTIF
        utilisateur.save()

        create_and_send_notification(
            recipient=utilisateur,
            title="Compte approuve",
            body="Votre compte a ete approuve. Vous pouvez maintenant acceder a toutes les fonctionnalites.",
            notification_type=NotificationType.COMPTE_APPROUVE,
            related_object_id=utilisateur.id,
        )

        serializer = self.get_serializer(utilisateur)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Garder l'ancien endpoint pour compatibilité mobile
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated], url_path='approuver-delegue')
    def approuver_delegue(self, request, pk=None):
        return self.approuver(request, pk)
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        self.perform_create(serializer)

        user = serializer.instance

        # Si un admin crée le compte, l'activer directement
        if request.user.is_authenticated:
            is_admin = request.user.roles.filter(nom_role=Role.SUPER_ADMIN).exists() or request.user.is_superuser
            if is_admin:
                user.statut = StatutCompte.ACTIF
                user.save()

        # Auto-activation si l'email est dans la whitelist
        if user.statut != StatutCompte.ACTIF:
            entry = EmailWhitelist.objects.filter(email__iexact=user.email).first()
            if entry:
                user.statut = StatutCompte.ACTIF
                user.save()

        headers = self.get_success_headers(serializer.data)
        # Re-serialize pour inclure le statut mis à jour
        data = self.get_serializer(serializer.instance).data
        return Response(data, status=status.HTTP_201_CREATED, headers=headers)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated], url_path='me')
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated], url_path='change-password')
    def change_password(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if not request.user.check_password(serializer.validated_data['old_password']):
            return Response({"detail": "Ancien mot de passe incorrect."}, status=status.HTTP_403_FORBIDDEN)

        nouveau = serializer.validated_data['new_password']
        if request.user.email.lower() == nouveau.lower():
            return Response(
                {"detail": "Le mot de passe ne peut pas etre votre adresse email."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.user.set_password(nouveau)
        # L'obligation imposee aux comptes crees par import est levee.
        request.user.doit_changer_mot_de_passe = False
        request.user.save()
        return Response({"detail": "Mot de passe modifié avec succès."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], permission_classes=[IsSuperAdmin],
            parser_classes=[MultiPartParser, FormParser, JSONParser], url_path='import-enseignants')
    def import_enseignants(self, request):
        """
        Creer des comptes enseignants depuis un fichier Excel.

        Colonnes reconnues : `email` (obligatoire), `nom_complet` (optionnel).
        Accepte donc aussi bien Import_Emails_Enseignants_*.xlsx que
        Import_Whitelist_*.xlsx.

        Le mot de passe initial est l'adresse email elle-meme, afin que les
        enseignants puissent se connecter sans echange prealable.
        """
        try:
            rows = parse_rows(request, required=['email'])
        except ExcelInvalide as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Simulation : on decrit les comptes qui seraient crees, sans rien ecrire.
        if est_simulation(request):
            apercu = PreviewReport()
            for line, values in rows:
                email = (values.get('email') or '').strip().lower()
                if not email:
                    continue
                valeurs = {'email': email, 'nom_complet': (values.get('nom_complet') or '').strip()}
                if '@' not in email:
                    apercu.ajouter(line, valeurs, statut=STATUT_ERREUR,
                                   message=f"Adresse email invalide : {email}")
                elif Utilisateur.objects.filter(email__iexact=email).exists():
                    apercu.ajouter(line, valeurs, statut=STATUT_DOUBLON,
                                   message="Compte deja existant, il ne sera pas modifie")
                else:
                    apercu.ajouter(line, valeurs, statut=STATUT_OK,
                                   message="Mot de passe initial : son adresse email")
            return Response(apercu.as_dict(), status=status.HTTP_200_OK)

        role_enseignant, _ = Role.objects.get_or_create(nom_role=Role.ENSEIGNANT)
        report = ImportReport()

        with transaction.atomic():
            for line, values in rows:
                email = (values.get('email') or '').strip().lower()
                if not email:
                    continue
                if '@' not in email:
                    report.error(line, f"Adresse email invalide : {email}")
                    continue

                nom_complet = (values.get('nom_complet') or '').strip()
                # "Adamou Hamza" -> prenom "Adamou", nom "Hamza"
                parts = nom_complet.split(' ', 1) if nom_complet else ['', '']
                first_name = parts[0]
                last_name = parts[1] if len(parts) > 1 else ''

                user = Utilisateur.objects.filter(email__iexact=email).first()
                if user:
                    # Compte deja present : on ne touche ni au mot de passe ni au statut,
                    # on garantit seulement le role Enseignant.
                    if not user.roles.filter(nom_role=Role.ENSEIGNANT).exists():
                        user.roles.add(role_enseignant)
                        report.updated += 1
                    else:
                        report.skipped += 1
                    continue

                user = Utilisateur(
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    statut=StatutCompte.ACTIF,
                    auth_provider=AuthProvider.PASSWORD,
                    # Le mot de passe initial est l'adresse email, connue de tous :
                    # le changement est exige des la premiere connexion.
                    doit_changer_mot_de_passe=True,
                )
                user.set_password(email)
                user.save()
                user.roles.add(role_enseignant)
                report.created += 1

        logger.info(
            f'Import enseignants par {request.user.email}: '
            f'{report.created} crees, {report.updated} mis a jour, {report.skipped} ignores'
        )
        return Response(report.as_dict(), status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated], url_path='register-fcm-token')
    def register_fcm_token(self, request):
        fcm_token = request.data.get('fcm_token')
        if not fcm_token:
            return Response({"detail": "Le champ 'fcm_token' est requis."}, status=status.HTTP_400_BAD_REQUEST)

        request.user.fcm_token = fcm_token
        request.user.save()

        return Response({"detail": "Token enregistré avec succès."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated], url_path='changer-niveau')
    def changer_niveau(self, request):
        """Permet a un delegue de changer son niveau/filiere lors d'une nouvelle annee academique."""
        user = request.user
        if not user.roles.filter(nom_role=Role.DELEGUE).exists():
            return Response({"detail": "Reserve aux delegues."}, status=status.HTTP_403_FORBIDDEN)

        from academic.models import Niveau, AnneeAcademique
        annee_active = AnneeAcademique.objects.filter(est_active=True).first()
        if not annee_active or not annee_active.est_configuree:
            return Response(
                {"detail": "Aucune annee academique active et configuree. Veuillez contacter l'administrateur."},
                status=status.HTTP_400_BAD_REQUEST
            )

        niveau_id = request.data.get('niveau_id')
        if not niveau_id:
            return Response({"detail": "Le champ 'niveau_id' est requis."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            niveau = Niveau.objects.select_related('filiere__departement').get(id=niveau_id)
        except Niveau.DoesNotExist:
            return Response({"detail": "Niveau introuvable."}, status=status.HTTP_404_NOT_FOUND)

        from academic.models import MandatDelegue, StatutMandat

        # Une declaration n'est pas une affectation : elle attend l'approbation
        # du chef, comme une inscription. Jusqu'ici un delegue se deplacait
        # seul vers n'importe quelle filiere, sans aucun controle.
        mandat, cree = MandatDelegue.objects.update_or_create(
            utilisateur=user,
            annee_academique=annee_active,
            defaults={
                'niveau': niveau,
                'statut': StatutMandat.EN_ATTENTE,
                'motif_refus': '',
                'approuve_par': None,
            },
        )

        # Prevenir le chef du departement concerne, s'il y en a un.
        departement = niveau.filiere.departement if niveau.filiere else None
        chef = getattr(departement, 'chef_departement', None) if departement else None
        if chef:
            create_and_send_notification(
                recipient=chef,
                title="Classe a valider",
                body=f"{user.get_full_name() or user.email} declare representer "
                     f"{niveau.filiere.nom_filiere} {niveau.nom_niveau} "
                     f"en {annee_active.libelle}.",
                notification_type='CLASSE_A_VALIDER',
            )

        return Response({
            "detail": "Votre classe a ete declaree. Elle doit etre validee par "
                      "le chef de departement avant que vous puissiez soumettre "
                      "des fiches.",
            "mandat": {
                "statut": mandat.statut,
                "annee": annee_active.libelle,
                "niveau": niveau.nom_niveau,
                "filiere": niveau.filiere.nom_filiere if niveau.filiere else None,
            },
        }, status=status.HTTP_200_OK if not cree else status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated],
            url_path='mandats-en-attente')
    def mandats_en_attente(self, request):
        """Classes declarees par les delegues et restant a valider."""
        from academic.models import AnneeAcademique, MandatDelegue, StatutMandat

        approbateur = request.user
        est_admin = (approbateur.roles.filter(nom_role=Role.SUPER_ADMIN).exists()
                     or approbateur.is_superuser)
        est_chef = approbateur.roles.filter(nom_role=Role.CHEF_DEPARTEMENT).exists()
        actif = approbateur.statut == StatutCompte.ACTIF or approbateur.is_superuser
        if not actif or not (est_admin or est_chef):
            return Response({"detail": "Acces refuse."}, status=status.HTTP_403_FORBIDDEN)

        annee = AnneeAcademique.objects.filter(est_active=True).first()
        if not annee:
            return Response([], status=status.HTTP_200_OK)

        mandats = (
            MandatDelegue.objects
            .filter(annee_academique=annee, statut=StatutMandat.EN_ATTENTE)
            .select_related('utilisateur', 'niveau__filiere__departement')
        )
        if est_chef and not est_admin:
            departement = getattr(approbateur, 'departement_gere', None)
            if not departement:
                return Response([], status=status.HTTP_200_OK)
            mandats = mandats.filter(niveau__filiere__departement=departement)

        resultat = []
        for m in mandats:
            # La classe de l'an passe aide le chef a trancher : un delegue qui
            # passe de L3 a M1 est attendu, un saut de filiere l'est moins.
            precedent = (
                MandatDelegue.objects
                .filter(utilisateur=m.utilisateur, statut=StatutMandat.APPROUVE)
                .exclude(annee_academique=annee)
                .select_related('niveau__filiere', 'annee_academique')
                .order_by('-annee_academique__libelle')
                .first()
            )
            resultat.append({
                'id': m.id,
                'utilisateur_id': m.utilisateur_id,
                'nom_complet': m.utilisateur.get_full_name() or m.utilisateur.email,
                'email': m.utilisateur.email,
                'niveau_id': m.niveau_id,
                'classe_demandee': f"{m.niveau.filiere.nom_filiere} {m.niveau.nom_niveau}"
                                   if m.niveau.filiere else m.niveau.nom_niveau,
                'classe_precedente': (
                    f"{precedent.niveau.filiere.nom_filiere} {precedent.niveau.nom_niveau} "
                    f"({precedent.annee_academique.libelle})"
                    if precedent and precedent.niveau.filiere else None
                ),
                'date_debut': m.date_debut,
            })
        return Response(resultat, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated],
            url_path='approuver-mandat')
    def approuver_mandat(self, request, pk=None):
        """Valider la classe declaree par un delegue pour l'annee en cours."""
        from academic.models import AnneeAcademique, MandatDelegue, StatutMandat

        approbateur = request.user
        est_admin = (approbateur.roles.filter(nom_role=Role.SUPER_ADMIN).exists()
                     or approbateur.is_superuser)
        est_chef = approbateur.roles.filter(nom_role=Role.CHEF_DEPARTEMENT).exists()
        actif = approbateur.statut == StatutCompte.ACTIF or approbateur.is_superuser
        if not actif or not (est_admin or est_chef):
            return Response({"detail": "Acces refuse."}, status=status.HTTP_403_FORBIDDEN)

        annee = AnneeAcademique.objects.filter(est_active=True).first()
        delegue = self.get_object()
        mandat = (
            MandatDelegue.objects
            .filter(utilisateur=delegue, annee_academique=annee)
            .select_related('niveau__filiere__departement')
            .first()
        )
        if not mandat:
            return Response({"detail": "Ce delegue n'a declare aucune classe pour "
                                       "l'annee en cours."},
                            status=status.HTTP_404_NOT_FOUND)

        if est_chef and not est_admin:
            departement = getattr(approbateur, 'departement_gere', None)
            attendu = mandat.niveau.filiere.departement if mandat.niveau.filiere else None
            if not departement or attendu != departement:
                return Response({"detail": "Cette classe ne releve pas de votre "
                                           "departement."},
                                status=status.HTTP_403_FORBIDDEN)

        mandat.statut = StatutMandat.APPROUVE
        mandat.motif_refus = ''
        mandat.approuve_par = approbateur
        mandat.save()

        # niveau_represente reste tenu a jour : les ecrans et les exports qui
        # s'appuient encore dessus continuent de fonctionner.
        delegue.niveau_represente = mandat.niveau
        delegue.save(update_fields=['niveau_represente'])

        create_and_send_notification(
            recipient=delegue,
            title="Classe validee",
            body=f"Votre classe pour {annee.libelle} a ete validee. "
                 f"Vous pouvez desormais soumettre vos fiches.",
            notification_type='CLASSE_VALIDEE',
        )
        return Response({"detail": "Classe validee."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated],
            url_path='refuser-mandat')
    def refuser_mandat(self, request, pk=None):
        """Refuser la classe declaree, en disant pourquoi."""
        from academic.models import AnneeAcademique, MandatDelegue, StatutMandat

        approbateur = request.user
        est_admin = (approbateur.roles.filter(nom_role=Role.SUPER_ADMIN).exists()
                     or approbateur.is_superuser)
        est_chef = approbateur.roles.filter(nom_role=Role.CHEF_DEPARTEMENT).exists()
        actif = approbateur.statut == StatutCompte.ACTIF or approbateur.is_superuser
        if not actif or not (est_admin or est_chef):
            return Response({"detail": "Acces refuse."}, status=status.HTTP_403_FORBIDDEN)

        motif = (request.data.get('motif') or '').strip()
        if not motif:
            return Response({"motif": "Indiquez le motif du refus."},
                            status=status.HTTP_400_BAD_REQUEST)

        annee = AnneeAcademique.objects.filter(est_active=True).first()
        delegue = self.get_object()
        mandat = MandatDelegue.objects.filter(
            utilisateur=delegue, annee_academique=annee
        ).first()
        if not mandat:
            return Response({"detail": "Aucune classe declaree."},
                            status=status.HTTP_404_NOT_FOUND)

        mandat.statut = StatutMandat.REFUSE
        mandat.motif_refus = motif
        mandat.approuve_par = approbateur
        mandat.save()

        create_and_send_notification(
            recipient=delegue,
            title="Classe refusee",
            body=f"Votre classe pour {annee.libelle} a ete refusee : {motif}",
            notification_type='CLASSE_REFUSEE',
        )
        return Response({"detail": "Classe refusee."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated], url_path='mes-utilisateurs')
    def mes_utilisateurs(self, request):
        """Retourne les utilisateurs pertinents pour un délégué: chef, enseignants (avec UEs), co-délégués."""
        user = request.user

        if not user.roles.filter(nom_role=Role.DELEGUE).exists():
            return Response({"detail": "Réservé aux délégués."}, status=status.HTTP_403_FORBIDDEN)

        niveau = user.niveau_represente
        if not niveau:
            return Response({"detail": "Aucun niveau représenté assigné."}, status=status.HTTP_400_BAD_REQUEST)

        # Nom de la classe
        classe_nom = f"{niveau.filiere.nom_filiere} {niveau.nom_niveau}"

        # Chef de département
        departement = niveau.filiere.departement
        chef = departement.chef_departement
        chef_data = None
        if chef:
            chef_data = {
                "id": chef.id,
                "nom_complet": chef.get_full_name(),
                "email": chef.email,
            }

        # Enseignants qui ont des UEs dans ce niveau, avec leurs UEs
        ues_du_niveau = UniteEnseignement.objects.filter(niveaux=niveau).prefetch_related('enseignants')
        enseignants_map = {}
        for ue in ues_du_niveau:
            for enseignant in ue.enseignants.all():
                if enseignant.id not in enseignants_map:
                    enseignants_map[enseignant.id] = {
                        "id": enseignant.id,
                        "nom_complet": enseignant.get_full_name(),
                        "email": enseignant.email,
                        "ues": [],
                    }
                enseignants_map[enseignant.id]["ues"].append({
                    "id": ue.id,
                    "code_ue": ue.code_ue,
                    "libelle_ue": ue.libelle_ue,
                })
        enseignants_data = list(enseignants_map.values())

        # Co-délégués du même niveau
        delegues = Utilisateur.objects.filter(
            niveau_represente=niveau,
            roles__nom_role=Role.DELEGUE,
            statut=StatutCompte.ACTIF,
        ).exclude(pk=user.pk)
        delegues_data = [
            {"id": d.id, "nom_complet": d.get_full_name(), "email": d.email}
            for d in delegues
        ]

        return Response({
            "classe": classe_nom,
            "chef": chef_data,
            "enseignants": enseignants_data,
            "delegues": delegues_data,
        })


    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated], url_path='reset-database')
    def reset_database(self, request):
        """Vider completement la base de donnees. Reserve au Super Admin avec confirmation par mot de passe."""
        user = request.user

        # Verifier que l'utilisateur est Super Admin
        if not (user.roles.filter(nom_role=Role.SUPER_ADMIN).exists() or user.is_superuser):
            return Response(
                {"detail": "Seul le Super Administrateur peut effectuer cette action."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Verifier le mot de passe
        password = request.data.get('password')
        if not password or not user.check_password(password):
            return Response(
                {"detail": "Mot de passe incorrect."},
                status=status.HTTP_403_FORBIDDEN,
            )

        from teaching.models import FicheSuivi, UniteEnseignement, PlanningCours
        from academic.models import (
            Semestre, AnneeAcademique, Niveau, Filiere, Departement, Faculte, Salle,
            HistoriqueChefDepartement,
        )
        from notifications.models import Notification

        # Ordre de suppression (respecter les FK)
        deleted = {}
        deleted['fiches'] = FicheSuivi.objects.all().delete()[0]
        deleted['planning'] = PlanningCours.objects.all().delete()[0]
        deleted['notifications'] = Notification.objects.all().delete()[0]
        deleted['historique_chefs'] = HistoriqueChefDepartement.objects.all().delete()[0]

        # Supprimer les relations M2M des UEs avant de supprimer
        for ue in UniteEnseignement.objects.all():
            ue.enseignants.clear()
            ue.niveaux.clear()
        deleted['ues'] = UniteEnseignement.objects.all().delete()[0]

        deleted['whitelist'] = EmailWhitelist.objects.all().delete()[0]
        deleted['semestres'] = Semestre.objects.all().delete()[0]
        deleted['annees'] = AnneeAcademique.objects.all().delete()[0]

        # Supprimer tous les utilisateurs SAUF l'admin actuel
        deleted['utilisateurs'] = Utilisateur.objects.exclude(pk=user.pk).delete()[0]

        # Niveaux -> Filieres -> Departements -> Facultes
        deleted['niveaux'] = Niveau.objects.all().delete()[0]
        deleted['filieres'] = Filiere.objects.all().delete()[0]

        # Detacher le chef avant de supprimer les departements
        Departement.objects.all().update(chef_departement=None)
        deleted['departements'] = Departement.objects.all().delete()[0]
        deleted['facultes'] = Faculte.objects.all().delete()[0]
        deleted['salles'] = Salle.objects.all().delete()[0]

        # Nettoyer les roles de l'admin (garder seulement Super Admin)
        role_admin = Role.objects.filter(nom_role=Role.SUPER_ADMIN).first()
        if role_admin:
            user.roles.set([role_admin])
        user.niveau_represente = None
        user.save()

        logger.warning("BASE DE DONNEES VIDEE par %s (id=%s)", user.email, user.id)

        return Response({
            "detail": "Base de donnees videe avec succes.",
            "supprime": deleted,
        }, status=status.HTTP_200_OK)


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsSuperAdmin]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        """
        Un visiteur ne voit que les roles qu'il peut demander.

        Le formulaire d'inscription a besoin de cette liste avant toute
        connexion, elle reste donc publique — mais amputee des roles
        privilegies, dont l'identifiant servait a se nommer administrateur
        lors d'une inscription Google.
        """
        utilisateur = self.request.user
        if utilisateur.is_authenticated and (
            utilisateur.is_superuser
            or utilisateur.roles.filter(nom_role=Role.SUPER_ADMIN).exists()
        ):
            return Role.objects.all()
        return Role.objects.filter(nom_role__in=[Role.DELEGUE, Role.ENSEIGNANT])
    

class EmailWhitelistViewSet(viewsets.ModelViewSet):
    serializer_class = EmailWhitelistSerializer
    permission_classes = [IsHoDOrSuperAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.roles.filter(nom_role=Role.SUPER_ADMIN).exists() or user.is_superuser:
            qs = EmailWhitelist.objects.all()
            dept = self.request.query_params.get('departement')
            if dept:
                qs = qs.filter(departement_id=dept)
            return qs
        # Chef de département → filtre par son département
        if hasattr(user, 'departement_gere') and user.departement_gere:
            return EmailWhitelist.objects.filter(departement=user.departement_gere)
        return EmailWhitelist.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        kwargs = {'ajoute_par': user}
        # Si chef, forcer le département au sien
        if not (user.roles.filter(nom_role=Role.SUPER_ADMIN).exists() or user.is_superuser):
            if hasattr(user, 'departement_gere') and user.departement_gere:
                kwargs['departement'] = user.departement_gere
        serializer.save(**kwargs)

    @action(detail=False, methods=['delete'], url_path='delete-all')
    def delete_all(self, request):
        """Supprimer tous les emails de la whitelist (scope par departement pour le chef)."""
        qs = self.get_queryset()
        count = qs.count()
        qs.delete()
        logger.warning(f'Whitelist videe ({count} emails) par {request.user.email}')
        return Response({'deleted': count}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'],
            parser_classes=[MultiPartParser, FormParser, JSONParser],
            url_path='import')
    def import_whitelist(self, request):
        """
        Importer des emails autorises depuis un fichier Excel.

        Colonnes reconnues : `email` (obligatoire), `role` et `nom_complet`
        (optionnels). Le departement est pris du parametre `departement`, ou
        force a celui du chef de departement connecte.
        """
        user = request.user
        est_admin = user.roles.filter(nom_role=Role.SUPER_ADMIN).exists() or user.is_superuser
        simulation = est_simulation(request)
        departement = None
        if est_admin:
            departement_id = request.data.get('departement')
            # Une simulation n'ecrit rien : elle n'a pas besoin du departement,
            # ce qui permet de previsualiser un fichier avant de l'avoir choisi.
            if not departement_id and not simulation:
                return Response(
                    {'detail': "Le champ 'departement' est requis."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if departement_id:
                departement = Departement.objects.filter(pk=departement_id).first()
                if not departement and not simulation:
                    return Response(
                        {'detail': "Departement introuvable."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
        else:
            departement = getattr(user, 'departement_gere', None)
            if not departement and not simulation:
                return Response(
                    {'detail': "Aucun departement associe a votre compte."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            rows = parse_rows(request, required=['email'])
        except ExcelInvalide as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        roles_valides = {choix[0] for choix in EmailWhitelist.ROLE_CHOICES}

        if simulation:
            apercu = PreviewReport()
            defaut = (request.data.get('role_defaut') or 'ENSEIGNANT').strip().upper()
            for line, values in rows:
                email = (values.get('email') or '').strip().lower()
                if not email:
                    continue
                role = (values.get('role') or defaut).strip().upper()
                valeurs = {'email': email, 'role': role}
                if '@' not in email:
                    apercu.ajouter(line, valeurs, statut=STATUT_ERREUR,
                                   message=f"Adresse email invalide : {email}")
                elif role not in roles_valides:
                    apercu.ajouter(line, valeurs, statut=STATUT_ERREUR,
                                   message=f"Role inconnu : {role}")
                elif EmailWhitelist.objects.filter(email=email).exists():
                    apercu.ajouter(line, valeurs, statut=STATUT_DOUBLON, message="Deja autorise")
                else:
                    apercu.ajouter(line, valeurs, statut=STATUT_OK)
            return Response(apercu.as_dict(), status=status.HTTP_200_OK)
        # Rôle applique aux lignes dont la colonne `role` est absente ou vide.
        role_defaut = (request.data.get('role_defaut') or 'ENSEIGNANT').strip().upper()
        report = ImportReport()

        with transaction.atomic():
            for line, values in rows:
                email = (values.get('email') or '').strip().lower()
                if not email:
                    continue
                if '@' not in email:
                    report.error(line, f"Adresse email invalide : {email}")
                    continue

                role_type = (values.get('role') or role_defaut).strip().upper()
                if role_type not in roles_valides:
                    report.error(
                        line,
                        f"Role inconnu : {role_type}. Valeurs acceptees : {', '.join(sorted(roles_valides))}.",
                    )
                    continue

                _, cree = EmailWhitelist.objects.get_or_create(
                    email=email,
                    defaults={
                        'role_type': role_type,
                        'departement': departement,
                        'ajoute_par': user,
                    },
                )
                if cree:
                    report.created += 1
                else:
                    report.skipped += 1

        logger.info(
            f'Import whitelist par {user.email}: '
            f'{report.created} ajoutes, {report.skipped} deja presents'
        )
        return Response(report.as_dict(), status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='bulk')
    def bulk_create(self, request):
        emails = request.data.get('emails', [])
        role_type = request.data.get('role_type')
        departement_id = request.data.get('departement')

        if not emails or not role_type:
            return Response(
                {'detail': 'Les champs emails et role_type sont requis.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        # Déterminer le département
        if user.roles.filter(nom_role=Role.SUPER_ADMIN).exists() or user.is_superuser:
            if not departement_id:
                return Response(
                    {'detail': 'Le champ departement est requis pour un admin.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            if hasattr(user, 'departement_gere') and user.departement_gere:
                departement_id = user.departement_gere.id
            else:
                return Response(
                    {'detail': "Vous n'êtes assigné à aucun département."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        created = []
        skipped = []
        for email in emails:
            email = email.strip().lower()
            if not email:
                continue
            if EmailWhitelist.objects.filter(email__iexact=email).exists():
                skipped.append(email)
                continue
            entry = EmailWhitelist.objects.create(
                email=email,
                role_type=role_type,
                departement_id=departement_id,
                ajoute_par=user,
            )
            created.append(email)

        return Response(
            {'created': created, 'skipped': skipped},
            status=status.HTTP_201_CREATED,
        )


class LoginRateThrottle(AnonRateThrottle):
    """Limite les tentatives de login a 5/minute"""
    scope = 'login'


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer
    throttle_classes = [LoginRateThrottle]


class GoogleAuthView(APIView):
    """
    Endpoint unique pour l'authentification Google.
    - POST { id_token } : login si l'utilisateur existe, sinon 404
    - POST { id_token, roles_ids, niveau_represente } : inscription + login
    """
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def _verify_firebase_token(self, token):
        """Verifie le token Firebase et retourne les infos utilisateur."""
        try:
            decoded = firebase_auth.verify_id_token(token, check_revoked=True)
            return decoded
        except firebase_auth.ExpiredIdTokenError as e:
            logger.warning(f'Firebase ID token expire: {e}')
            return None
        except firebase_auth.RevokedIdTokenError as e:
            logger.warning(f'Firebase ID token revoque: {e}')
            return None
        except firebase_auth.InvalidIdTokenError as e:
            logger.warning(f'Firebase ID token invalide: {e}')
            return None
        except firebase_auth.CertificateFetchError as e:
            logger.error(f'Firebase impossible de recuperer les certificats Google: {e}')
            return None
        except Exception as e:
            logger.error(f'Erreur verification Firebase token: {type(e).__name__}: {e}')
            return None

    def _generate_tokens(self, user):
        """Genere les tokens JWT pour un utilisateur."""
        refresh = RefreshToken.for_user(user)
        serializer = UtilisateurSerializer(user)
        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': serializer.data,
        }

    def post(self, request):
        token = request.data.get('id_token')
        if not token:
            return Response(
                {'detail': "Le champ 'id_token' est requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        decoded = self._verify_firebase_token(token)
        if not decoded:
            logger.error(f'Token Firebase rejete. Token length={len(token)}, first_50={token[:50]}')
            return Response(
                {'detail': 'Token Firebase invalide.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        email = decoded.get('email', '').lower()
        firebase_name = decoded.get('name', '')
        # Firebase stocke le nom complet dans 'name', on le split
        name_parts = firebase_name.split(' ', 1) if firebase_name else ['', '']
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        if not email:
            return Response(
                {'detail': "Impossible de recuperer l'email depuis le token Google."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verifier si l'utilisateur existe
        try:
            user = Utilisateur.objects.get(email=email)
            # Utilisateur existant -> login
            data = self._generate_tokens(user)
            return Response(data, status=status.HTTP_200_OK)
        except Utilisateur.DoesNotExist:
            pass

        # Utilisateur n'existe pas
        roles_ids = request.data.get('roles_ids')

        if not roles_ids:
            # Pas de donnees d'inscription -> indiquer que l'utilisateur n'existe pas
            return Response(
                {
                    'status': 'user_not_found',
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Inscription Google
        niveau_represente = request.data.get('niveau_represente')

        try:
            # Une inscription libre ne peut donner que les deux roles qui
            # s'auto-attribuent. Sans ce filtre, n'importe quel compte Google
            # obtenait le role demande dans la requete : l'identifiant du role
            # Super Administrateur etant lisible publiquement, il suffisait de
            # le passer ici pour devenir administrateur du systeme, jeton
            # compris, en un seul appel.
            roles = Role.objects.filter(
                id__in=roles_ids, nom_role__in=[Role.DELEGUE, Role.ENSEIGNANT]
            )
            if not roles.exists():
                return Response(
                    {'detail': "Seuls les roles Delegue et Enseignant peuvent etre "
                               "demandes a l'inscription."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validation: delegue doit avoir un niveau
            is_delegue = roles.filter(nom_role=Role.DELEGUE).exists()
            if is_delegue and not niveau_represente:
                return Response(
                    {'niveau_represente': 'Ce champ est obligatoire pour un delegue.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user = Utilisateur(
                email=email,
                first_name=first_name,
                last_name=last_name,
                statut=StatutCompte.EN_ATTENTE,
                auth_provider=AuthProvider.GOOGLE,
                niveau_represente_id=niveau_represente,
            )
            user.set_unusable_password()
            user.save()
            user.roles.set(roles)

            # Auto-activation si l'email est dans la whitelist
            entry = EmailWhitelist.objects.filter(email__iexact=user.email).first()
            if entry:
                user.statut = StatutCompte.ACTIF
                user.save()

            data = self._generate_tokens(user)
            return Response(data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f'Erreur inscription Google: {e}')
            return Response(
                {'detail': "Erreur lors de la creation du compte."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
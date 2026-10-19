from rest_framework import serializers
from .models import Utilisateur, Role, StatutCompte, EmailWhitelist
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class PasswordConfirmationSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'nom_role']


class UtilisateurSerializer(serializers.ModelSerializer):
    roles = RoleSerializer(many=True, read_only=True)
    roles_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Role.objects.all(),
        write_only=True,
        source='roles',
        required=False
    )

    password = serializers.CharField(write_only=True, required=False)
    nom_departement = serializers.SerializerMethodField()
    # Le niveau represente n'etait expose que par son identifiant : impossible,
    # pour un chef examinant une demande, de savoir de quelle classe releve le
    # delegue. On renvoie la chaine complete, en lecture seule.
    classe = serializers.SerializerMethodField()
    enseignements = serializers.SerializerMethodField()
    mandat = serializers.SerializerMethodField()

    class Meta:
        model = Utilisateur
        fields = [
            'id', 'email', 'first_name', 'last_name', 'password',
            'statut', 'auth_provider', 'roles', 'roles_ids', 'niveau_represente', 'fcm_token',
            'is_superuser', 'is_staff', 'nom_departement', 'doit_changer_mot_de_passe',
            'classe', 'enseignements', 'mandat'
        ]
        read_only_fields = [
            'statut', 'auth_provider', 'is_superuser', 'is_staff',
            'doit_changer_mot_de_passe',
        ]

    def get_classe(self, obj):
        """
        Classe representee cette annee par un delegue.

        Elle est lue sur le mandat de l'annee active, et non plus sur
        niveau_represente : ce champ ne portait aucune annee, et survivait donc
        au changement d'annee en designant une classe que le delegue avait
        quittee.
        """
        if not obj.roles.filter(nom_role=Role.DELEGUE).exists():
            return None
        niveau = obj.classe_actuelle()
        if not niveau:
            return None
        filiere = niveau.filiere
        departement = filiere.departement if filiere else None
        return {
            'niveau_id': niveau.id,
            'niveau': niveau.nom_niveau,
            'filiere_id': filiere.id if filiere else None,
            'filiere': filiere.nom_filiere if filiere else None,
            'departement_id': departement.id if departement else None,
            'departement': departement.nom_departement if departement else None,
            'libelle': ' > '.join(
                p for p in [
                    departement.nom_departement if departement else None,
                    filiere.nom_filiere if filiere else None,
                    niveau.nom_niveau,
                ] if p
            ),
        }

    def get_enseignements(self, obj):
        """UEs enseignees et niveaux couverts, pour examiner un enseignant."""
        if not obj.roles.filter(nom_role=Role.ENSEIGNANT).exists():
            return None
        # Borne a l'annee active : la reconduction recopie les UEs d'une
        # annee sur l'autre, si bien qu'un enseignant verrait sinon les siennes
        # en double des le premier changement d'annee.
        ues = obj.ues_enseignees.filter(
            semestre_obj__annee_academique__est_active=True
        ).select_related('semestre_obj').prefetch_related('niveaux')
        niveaux = sorted({
            n.nom_niveau for ue in ues for n in ue.niveaux.all()
        })
        return {
            'nombre_ues': len(ues),
            'ues': [
                {'id': ue.id, 'code': ue.code_ue, 'libelle': ue.libelle_ue}
                for ue in ues[:20]
            ],
            'niveaux': niveaux,
        }

    def get_mandat(self, obj):
        """
        Etat du mandat de delegue pour l'annee en cours.

        `a_renouveler` est ce qui permet a l'interface de demander sa classe a
        un delegue des l'ouverture d'une nouvelle annee, plutot que de lui
        montrer les cours d'un niveau qu'il a quitte.
        """
        from academic.models import AnneeAcademique, MandatDelegue

        if not obj.roles.filter(nom_role=Role.DELEGUE).exists():
            return None

        annee = AnneeAcademique.objects.filter(est_active=True).first()
        if not annee:
            return {'annee': None, 'statut': None, 'a_renouveler': False,
                    'niveau': None, 'libelle': None}

        mandat = (
            MandatDelegue.objects
            .filter(utilisateur=obj, annee_academique=annee)
            .select_related('niveau__filiere')
            .first()
        )
        if not mandat:
            return {'annee': annee.libelle, 'statut': None, 'a_renouveler': True,
                    'niveau': None, 'libelle': None}

        niveau = mandat.niveau
        filiere = niveau.filiere if niveau else None
        return {
            'annee': annee.libelle,
            'statut': mandat.statut,
            # Un mandat refuse est a redeclarer ; un mandat en attente ne l'est
            # pas, le delegue a deja fait ce qu'on attendait de lui.
            'a_renouveler': mandat.statut == 'REFUSE',
            'niveau_id': niveau.id if niveau else None,
            'niveau': niveau.nom_niveau if niveau else None,
            'filiere': filiere.nom_filiere if filiere else None,
            'libelle': f"{filiere.nom_filiere} {niveau.nom_niveau}" if filiere and niveau else None,
            'motif_refus': mandat.motif_refus or None,
        }

    def get_nom_departement(self, obj):
        dept = getattr(obj, 'departement_gere', None)
        if dept:
            return dept.nom_departement
        return None

    def validate(self, attrs):
        # Password obligatoire uniquement a la creation
        if not self.instance and not attrs.get('password'):
            raise serializers.ValidationError({
                'password': 'Le mot de passe est obligatoire lors de la creation.'
            })

        # Validation du niveau_represente pour les delegues
        roles = attrs.get('roles')
        niveau = attrs.get('niveau_represente')

        if roles:
            is_delegue = any(role.nom_role == Role.DELEGUE for role in roles)

            if is_delegue and not niveau:
                if self.instance and self.instance.niveau_represente:
                    pass  # Le niveau existe deja sur l'instance
                else:
                    raise serializers.ValidationError({
                        "niveau_represente": "Ce champ est obligatoire pour un utilisateur ayant le rôle de Délégué."
                    })

        # Empecher les non-admins d'assigner des roles privilegies
        if roles:
            request = self.context.get('request')
            if request:
                privileged_roles = [Role.SUPER_ADMIN, Role.CHEF_DEPARTEMENT]
                has_privileged = any(role.nom_role in privileged_roles for role in roles)

                if has_privileged:
                    is_admin = (
                        request.user.is_authenticated and (
                            request.user.is_superuser or
                            request.user.roles.filter(nom_role=Role.SUPER_ADMIN).exists()
                        )
                    )
                    if not is_admin:
                        raise serializers.ValidationError({
                            "roles_ids": "Seul un Super Administrateur peut assigner les roles privilegies."
                        })

        return attrs

    def create(self, validated_data):
        roles_data = validated_data.pop('roles', [])

        # Tous les comptes créés par inscription démarrent EN_ATTENTE
        validated_data['statut'] = StatutCompte.EN_ATTENTE

        user = Utilisateur.objects.create_user(**validated_data)

        if roles_data:
            user.roles.set(roles_data)

        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)

        # Gere la mise a jour des roles si elle est fournie
        roles_data = validated_data.pop('roles', None)

        if roles_data is not None:
            instance.roles.set(roles_data)

        # Le chef ou l'administrateur peut corriger directement la classe d'un
        # delegue. Cette correction fait autorite : elle vaut mandat approuve
        # pour l'annee en cours, faute de quoi elle n'aurait aucun effet sur ce
        # que le delegue voit, la classe etant desormais lue sur le mandat.
        niveau_impose = validated_data.get('niveau_represente', serializers.empty)

        instance = super().update(instance, validated_data)

        if niveau_impose is not serializers.empty and niveau_impose is not None:
            from academic.models import AnneeAcademique, MandatDelegue, StatutMandat

            annee = AnneeAcademique.objects.filter(est_active=True).first()
            if annee and instance.roles.filter(nom_role=Role.DELEGUE).exists():
                MandatDelegue.objects.update_or_create(
                    utilisateur=instance,
                    annee_academique=annee,
                    defaults={
                        'niveau': niveau_impose,
                        'statut': StatutMandat.APPROUVE,
                        'motif_refus': '',
                    },
                )

        if password:
            instance.set_password(password)
            instance.save()

        return instance


class EmailWhitelistSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailWhitelist
        fields = ['id', 'email', 'role_type', 'departement', 'ajoute_par', 'date_ajout']
        read_only_fields = ['id', 'ajoute_par', 'date_ajout']


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        return token

    def validate(self, attrs):
        data = super().validate(attrs)

        # Auto-assign Super Administrateur role to Django superusers
        if self.user.is_superuser and not self.user.roles.exists():
            admin_role = Role.objects.filter(nom_role=Role.SUPER_ADMIN).first()
            if admin_role:
                self.user.roles.add(admin_role)

        serializer = UtilisateurSerializer(self.user)
        data['user'] = serializer.data

        return data

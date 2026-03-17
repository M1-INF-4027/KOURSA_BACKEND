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

    class Meta:
        model = Utilisateur
        fields = [
            'id', 'email', 'first_name', 'last_name', 'password',
            'statut', 'auth_provider', 'roles', 'roles_ids', 'niveau_represente', 'fcm_token',
            'is_superuser', 'is_staff', 'nom_departement'
        ]
        read_only_fields = ['statut', 'auth_provider', 'is_superuser', 'is_staff']

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

        instance = super().update(instance, validated_data)

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

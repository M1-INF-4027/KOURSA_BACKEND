from rest_framework import serializers
from .models import Utilisateur, Role, StatutCompte
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class PasswordConfirmationSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})


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

    class Meta:
        model = Utilisateur
        fields = [
            'id', 'email', 'first_name', 'last_name', 'password',
            'statut', 'roles', 'roles_ids', 'niveau_represente', 'fcm_token',
            'is_superuser', 'is_staff'
        ]
        read_only_fields = ['statut', 'is_superuser', 'is_staff']

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
                raise serializers.ValidationError({
                    "niveau_represente": "Ce champ est obligatoire pour un utilisateur ayant le rôle de Délégué."
                })

        return attrs

    def create(self, validated_data):
        roles_data = validated_data.pop('roles', [])

        # Determiner le statut initial selon le role
        statut_final = StatutCompte.EN_ATTENTE

        is_enseignant = any(role.nom_role == Role.ENSEIGNANT for role in roles_data)

        if is_enseignant:
            statut_final = StatutCompte.ACTIF

        validated_data['statut'] = statut_final

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

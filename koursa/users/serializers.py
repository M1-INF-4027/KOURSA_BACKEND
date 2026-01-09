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
        source='roles'
    )
    
    password = serializers.CharField(write_only=True)

    class Meta:
        model = Utilisateur
        fields = [
            'id', 'email', 'first_name', 'last_name', 'password',
            'statut', 'roles', 'roles_ids', 'niveau_represente', 'fcm_token'
        ]
        read_only_fields = ['statut']

    def create(self, validated_data):
        roles_data = validated_data.pop('roles')
        
    
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
        roles_data = validated_data.pop('roles', None)
        
        if roles_data is not None:
            instance.roles.set(roles_data)

        instance = super().update(instance, validated_data)

        if password:
            instance.set_password(password)
        
        instance.save()
        return instance
    
    def validate(self, data):
        roles = data.get('roles')
        niveau = data.get('niveau_represente')

        if roles:
            is_delegue = any(role.nom_role == Role.DELEGUE for role in roles)
            
            if is_delegue and not niveau:
                raise serializers.ValidationError(
                    {"niveau_represente": "Ce champ est obligatoire pour un utilisateur ayant le rôle de Délégué."}
                )
        
        return data
    
class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        
        serializer = UtilisateurSerializer(self.user)
        data['user'] = serializer.data
        
        return data
from rest_framework import serializers
from .models import Utilisateur, Role

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
            'statut', 'roles', 'roles_ids', 'niveau_represente'
        ]
        read_only_fields = ['statut']

    def create(self, validated_data):
        roles_data = validated_data.pop('roles')
        
        user = Utilisateur.objects.create_user(**validated_data)
        
        if roles_data:
            user.roles.set(roles_data)
            
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        
        # Gère la mise à jour des rôles si elle est fournie
        roles_data = validated_data.pop('roles', None)
        if roles_data is not None:
            instance.roles.set(roles_data)

        instance = super().update(instance, validated_data)

        if password:
            instance.set_password(password)
        
        instance.save()
        return instance
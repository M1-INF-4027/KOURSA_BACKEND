from rest_framework import serializers
from .models import Utilisateur, Role


class UtilisateurSerializer(serializers.ModelSerializer):
    roles = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Role.objects.all()
    )

    password = serializers.CharField(write_only=True)

    class Meta:
        model = Utilisateur
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'password',
            'statut',
            'roles',
            'niveau_represente',
            'is_active'
        ]

    def create(self, validated_data):
        roles = validated_data.pop('roles', [])
        password = validated_data.pop('password')

        user = Utilisateur.objects.create_user(
            password=password,
            **validated_data
        )
        user.roles.set(roles)
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        roles = validated_data.pop('roles', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)

        if roles is not None:
            instance.roles.set(roles)

        instance.save()
        return instance

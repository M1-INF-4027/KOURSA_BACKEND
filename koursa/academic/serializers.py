from rest_framework import serializers
from .models import Faculte, Departement, Filiere, Niveau

class FaculteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Faculte
        fields = ['id', 'nom_faculte']

class DepartementSerializer(serializers.ModelSerializer):
    nom_faculte = serializers.CharField(source='faculte.nom_faculte', read_only=True)
    nom_chef = serializers.CharField(source='chef_departement.__str__', read_only=True, default=None)

    class Meta:
        model = Departement
        fields = ['id', 'nom_departement', 'faculte', 'nom_faculte', 'chef_departement', 'nom_chef']

class FiliereSerializer(serializers.ModelSerializer):
    nom_departement = serializers.CharField(source='departement.nom_departement', read_only=True)
    
    class Meta:
        model = Filiere
        fields = ['id', 'nom_filiere', 'departement', 'nom_departement']

class NiveauSerializer(serializers.ModelSerializer):
    nom_filiere = serializers.CharField(source='filiere.nom_filiere', read_only=True)

    class Meta:
        model = Niveau
        fields = ['id', 'nom_niveau', 'filiere', 'nom_filiere']
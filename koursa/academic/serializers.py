import re
from rest_framework import serializers
from .models import Faculte, Departement, Filiere, Niveau, AnneeAcademique, Semestre, HistoriqueChefDepartement

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
    faculte = serializers.IntegerField(source='departement.faculte_id', read_only=True)
    nom_faculte = serializers.CharField(source='departement.faculte.nom_faculte', read_only=True)

    class Meta:
        model = Filiere
        fields = ['id', 'nom_filiere', 'departement', 'nom_departement', 'faculte', 'nom_faculte']

class NiveauSerializer(serializers.ModelSerializer):
    nom_filiere = serializers.CharField(source='filiere.nom_filiere', read_only=True)

    class Meta:
        model = Niveau
        fields = ['id', 'nom_niveau', 'filiere', 'nom_filiere']


class SemestreSerializer(serializers.ModelSerializer):
    annee_label = serializers.CharField(source='annee_academique.libelle', read_only=True)

    class Meta:
        model = Semestre
        fields = ['id', 'annee_academique', 'annee_label', 'numero', 'date_debut', 'date_fin', 'est_actif']


class AnneeAcademiqueSerializer(serializers.ModelSerializer):
    semestres = SemestreSerializer(many=True, read_only=True)

    class Meta:
        model = AnneeAcademique
        fields = ['id', 'libelle', 'est_active', 'est_configuree', 'date_creation', 'semestres']
        read_only_fields = ['date_creation']


class CreateAnneeAcademiqueSerializer(serializers.Serializer):
    """Utilise par le wizard pour creer une annee avec ses 2 semestres."""
    libelle = serializers.CharField(max_length=9)
    s1_date_debut = serializers.DateField()
    s1_date_fin = serializers.DateField()
    s2_date_debut = serializers.DateField()
    s2_date_fin = serializers.DateField()

    def validate_libelle(self, value):
        if not re.match(r'^\d{4}-\d{4}$', value):
            raise serializers.ValidationError("Format attendu: YYYY-YYYY (ex: 2025-2026)")
        if AnneeAcademique.objects.filter(libelle=value).exists():
            raise serializers.ValidationError("Cette annee academique existe deja.")
        return value

    def validate(self, attrs):
        if attrs['s1_date_fin'] <= attrs['s1_date_debut']:
            raise serializers.ValidationError({'s1_date_fin': 'Doit etre apres la date de debut du S1.'})
        if attrs['s2_date_fin'] <= attrs['s2_date_debut']:
            raise serializers.ValidationError({'s2_date_fin': 'Doit etre apres la date de debut du S2.'})
        if attrs['s2_date_debut'] <= attrs['s1_date_fin']:
            raise serializers.ValidationError({'s2_date_debut': 'Le S2 doit commencer apres la fin du S1.'})
        return attrs


class HistoriqueChefSerializer(serializers.ModelSerializer):
    nom_utilisateur = serializers.SerializerMethodField()
    nom_departement = serializers.CharField(source='departement.nom_departement', read_only=True)
    annee_label = serializers.CharField(source='annee_academique.libelle', read_only=True)

    class Meta:
        model = HistoriqueChefDepartement
        fields = [
            'id', 'departement', 'nom_departement', 'utilisateur', 'nom_utilisateur',
            'annee_academique', 'annee_label', 'date_debut', 'date_fin'
        ]

    def get_nom_utilisateur(self, obj):
        if obj.utilisateur:
            return f"{obj.utilisateur.first_name} {obj.utilisateur.last_name}"
        return None
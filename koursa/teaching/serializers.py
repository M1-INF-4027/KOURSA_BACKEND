from rest_framework import serializers
from .models import UniteEnseignement, FicheSuivi

class UniteEnseignementSerializer(serializers.ModelSerializer):
    class Meta:
        model = UniteEnseignement
        fields = [
            'id', 'code_ue', 'libelle_ue', 'semestre', 
            'enseignants', 
            'niveaux'      
        ]

class FicheSuiviSerializer(serializers.ModelSerializer):
    nom_ue = serializers.CharField(source='ue.libelle_ue', read_only=True)
    nom_delegue = serializers.CharField(source='delegue.__str__', read_only=True)
    nom_enseignant = serializers.CharField(source='enseignant.__str__', read_only=True)

    class Meta:
        model = FicheSuivi
        fields = [
            'id', 'ue', 'nom_ue', 'delegue', 'nom_delegue', 'enseignant', 'nom_enseignant',
            'date_cours', 'heure_debut', 'heure_fin', 'duree', 'salle', 'type_seance',
            'titre_chapitre', 'contenu_aborde', 'statut', 'motif_refus', 
            'date_soumission', 'date_validation'
        ]
        read_only_fields = ['duree', 'statut', 'date_soumission', 'date_validation']

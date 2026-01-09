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
    nom_delegue = serializers.SerializerMethodField()
    nom_enseignant = serializers.SerializerMethodField()

    class Meta:
        model = FicheSuivi
        fields = [
            'id', 'ue', 'nom_ue', 'delegue', 'nom_delegue', 'enseignant', 'nom_enseignant',
            'date_cours', 'heure_debut', 'heure_fin', 'duree', 'salle', 'type_seance',
            'titre_chapitre', 'contenu_aborde', 'statut', 'motif_refus',
            'date_soumission', 'date_validation'
        ]
        read_only_fields = ['duree', 'date_soumission', 'date_validation']

    def get_nom_delegue(self, obj):
        return str(obj.delegue) if obj.delegue else None

    def get_nom_enseignant(self, obj):
        return str(obj.enseignant) if obj.enseignant else None


class ValidationFicheSerializer(serializers.Serializer):
    """Serializer pour valider ou refuser une fiche"""
    action = serializers.ChoiceField(choices=['valider', 'refuser'])
    motif_refus = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs['action'] == 'refuser' and not attrs.get('motif_refus'):
            raise serializers.ValidationError({
                'motif_refus': 'Le motif de refus est obligatoire.'
            })
        return attrs

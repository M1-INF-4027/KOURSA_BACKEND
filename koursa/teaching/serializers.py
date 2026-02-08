from rest_framework import serializers
from .models import UniteEnseignement, FicheSuivi
from datetime import date


class EnseignantSimpleSerializer(serializers.Serializer):
    """Serializer simplifié pour les enseignants dans UniteEnseignement"""
    id = serializers.IntegerField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    nom_complet = serializers.SerializerMethodField()

    def get_nom_complet(self, obj):
        return f"{obj.first_name} {obj.last_name}"


class NiveauSimpleSerializer(serializers.Serializer):
    """Serializer simplifié pour les niveaux dans UniteEnseignement"""
    id = serializers.IntegerField()
    nom_niveau = serializers.CharField()
    filiere_nom = serializers.SerializerMethodField()

    def get_filiere_nom(self, obj):
        return obj.filiere.nom_filiere if obj.filiere else None


class UniteEnseignementSerializer(serializers.ModelSerializer):
    enseignants_details = EnseignantSimpleSerializer(source='enseignants', many=True, read_only=True)
    niveaux_details = NiveauSimpleSerializer(source='niveaux', many=True, read_only=True)

    class Meta:
        model = UniteEnseignement
        fields = [
            'id', 'code_ue', 'libelle_ue', 'semestre',
            'enseignants', 'enseignants_details',
            'niveaux', 'niveaux_details'
        ]


class FicheSuiviSerializer(serializers.ModelSerializer):
    nom_ue = serializers.CharField(source='ue.libelle_ue', read_only=True)
    code_ue = serializers.CharField(source='ue.code_ue', read_only=True)
    semestre = serializers.IntegerField(source='ue.semestre', read_only=True)
    nom_delegue = serializers.SerializerMethodField()
    nom_enseignant = serializers.SerializerMethodField()
    classe = serializers.SerializerMethodField()
    niveaux_details = serializers.SerializerMethodField()

    class Meta:
        model = FicheSuivi
        fields = [
            'id', 'ue', 'code_ue', 'nom_ue', 'semestre',
            'classe', 'niveaux_details',
            'delegue', 'nom_delegue', 'enseignant', 'nom_enseignant',
            'date_cours', 'heure_debut', 'heure_fin', 'duree', 'salle', 'type_seance',
            'titre_chapitre', 'contenu_aborde', 'statut', 'motif_refus',
            'date_soumission', 'date_validation'
        ]
        read_only_fields = ['duree', 'statut', 'date_soumission', 'date_validation', 'delegue']

    def get_nom_delegue(self, obj):
        return f"{obj.delegue.first_name} {obj.delegue.last_name}" if obj.delegue else None

    def get_nom_enseignant(self, obj):
        return f"{obj.enseignant.first_name} {obj.enseignant.last_name}" if obj.enseignant else None

    def get_niveaux_details(self, obj):
        if obj.ue:
            return [
                {'nom_niveau': n.nom_niveau, 'filiere_nom': n.filiere.nom_filiere}
                for n in obj.ue.niveaux.select_related('filiere').all()
            ]
        return []

    def get_classe(self, obj):
        if obj.ue:
            niveaux = obj.ue.niveaux.select_related('filiere').all()
            labels = [f"{n.filiere.nom_filiere} {n.nom_niveau}" for n in niveaux]
            return ', '.join(labels) if labels else None
        return None

    def validate(self, attrs):
        """Validation personnalisée des données de la fiche de suivi"""
        heure_debut = attrs.get('heure_debut')
        heure_fin = attrs.get('heure_fin')
        date_cours = attrs.get('date_cours')
        ue = attrs.get('ue')
        enseignant = attrs.get('enseignant')

        # Vérifier que l'heure de fin est après l'heure de début
        if heure_debut and heure_fin:
            if heure_fin <= heure_debut:
                raise serializers.ValidationError({
                    'heure_fin': "L'heure de fin doit être postérieure à l'heure de début."
                })

        # Vérifier que la date du cours n'est pas dans le futur lointain (max 7 jours)
        if date_cours:
            from datetime import timedelta
            max_date = date.today() + timedelta(days=7)
            if date_cours > max_date:
                raise serializers.ValidationError({
                    'date_cours': "La date du cours ne peut pas être plus de 7 jours dans le futur."
                })

        # Vérifier que l'enseignant est bien assigné à l'UE
        if ue and enseignant:
            if not ue.enseignants.filter(id=enseignant.id).exists():
                raise serializers.ValidationError({
                    'enseignant': "Cet enseignant n'est pas assigné à cette unité d'enseignement."
                })

        return attrs


class ValidationTokenSerializer(serializers.Serializer):
    """Serializer pour la validation par token JWT"""
    validation_token = serializers.CharField()


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

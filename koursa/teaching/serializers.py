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
    semestre_info = serializers.SerializerMethodField()
    semestre = serializers.IntegerField(required=False)

    class Meta:
        model = UniteEnseignement
        fields = [
            'id', 'code_ue', 'libelle_ue', 'semestre', 'semestre_obj',
            'semestre_info', 'enseignants', 'enseignants_details',
            'niveaux', 'niveaux_details'
        ]
        # Desactiver le validateur unique_together auto-genere par DRF
        # car semestre_obj est nullable et on gere la validation manuellement
        validators = []

    def get_semestre_info(self, obj):
        if obj.semestre_obj:
            return {
                'id': obj.semestre_obj.id,
                'numero': obj.semestre_obj.numero,
                'annee': obj.semestre_obj.annee_academique.libelle,
            }
        return None

    def validate_code_ue(self, value):
        return value.upper()

    def validate(self, attrs):
        # Auto-populate semestre from semestre_obj if not provided
        semestre_obj = attrs.get('semestre_obj')
        if semestre_obj and not attrs.get('semestre'):
            attrs['semestre'] = semestre_obj.numero
        elif not attrs.get('semestre') and not semestre_obj:
            attrs['semestre'] = 1  # Default

        # Validation unique_together manuelle (code_ue + semestre_obj)
        code_ue = attrs.get('code_ue', getattr(self.instance, 'code_ue', None))
        sem_obj = attrs.get('semestre_obj', getattr(self.instance, 'semestre_obj', None))
        qs = UniteEnseignement.objects.filter(code_ue=code_ue, semestre_obj=sem_obj)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                {'code_ue': f"Une UE avec le code '{code_ue}' existe deja pour ce semestre."}
            )

        return attrs


class FicheSuiviSerializer(serializers.ModelSerializer):
    nom_ue = serializers.CharField(source='ue.libelle_ue', read_only=True)
    code_ue = serializers.CharField(source='ue.code_ue', read_only=True)
    semestre = serializers.IntegerField(source='ue.semestre', read_only=True)
    nom_delegue = serializers.SerializerMethodField()
    nom_enseignant = serializers.SerializerMethodField()
    classe = serializers.SerializerMethodField()
    niveaux_details = serializers.SerializerMethodField()

    nom_salle = serializers.CharField(source='salle.nom_salle', read_only=True, default=None)

    semestre_info = serializers.SerializerMethodField()

    class Meta:
        model = FicheSuivi
        fields = [
            'id', 'ue', 'code_ue', 'nom_ue', 'semestre',
            'semestre_info', 'classe', 'niveaux_details',
            'delegue', 'nom_delegue', 'enseignant', 'nom_enseignant',
            'date_cours', 'heure_debut', 'heure_fin', 'duree', 'salle', 'nom_salle', 'type_seance',
            'titre_chapitre', 'contenu_aborde', 'statut', 'motif_refus',
            'date_soumission', 'date_validation'
        ]
        read_only_fields = ['duree', 'statut', 'date_soumission', 'date_validation', 'semestre']

    def get_semestre_info(self, obj):
        if obj.semestre:
            return {
                'id': obj.semestre.id,
                'numero': obj.semestre.numero,
                'annee': obj.semestre.annee_academique.libelle,
            }
        return None

    def get_nom_delegue(self, obj):
        return f"{obj.delegue.first_name} {obj.delegue.last_name}" if obj.delegue else None

    def get_nom_enseignant(self, obj):
        return f"{obj.enseignant.first_name} {obj.enseignant.last_name}" if obj.enseignant else None

    def get_niveaux_details(self, obj):
        if obj.ue:
            # Use prefetched data if available (from view's prefetch_related)
            niveaux = obj.ue.niveaux.all()
            return [
                {'nom_niveau': n.nom_niveau, 'filiere_nom': n.filiere.nom_filiere if n.filiere else None}
                for n in niveaux
            ]
        return []

    def get_classe(self, obj):
        if obj.ue:
            niveaux = obj.ue.niveaux.all()
            labels = [f"{n.filiere.nom_filiere} {n.nom_niveau}" for n in niveaux if n.filiere]
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

        # Vérifier que la date du cours est dans une plage raisonnable
        if date_cours:
            from datetime import timedelta
            request = self.context.get('request')
            is_chef = False
            if request and request.user and request.user.is_authenticated:
                from users.models import Role
                is_chef = request.user.roles.filter(
                    nom_role__in=[Role.CHEF_DEPARTEMENT, Role.SUPER_ADMIN]
                ).exists() or request.user.is_superuser

            max_date = date.today() + timedelta(days=7)
            if date_cours > max_date:
                raise serializers.ValidationError({
                    'date_cours': "La date du cours ne peut pas être plus de 7 jours dans le futur."
                })

            # Les chefs/admins n'ont pas de restriction de date dans le passe
            if not is_chef:
                min_date = date.today() - timedelta(days=3)
                if date_cours < min_date:
                    raise serializers.ValidationError({
                        'date_cours': "La date du cours ne peut pas depasser 3 jours dans le passe. Contactez votre chef de departement pour creer cette fiche."
                    })

        # Vérifier que l'enseignant est bien assigné à l'UE
        if ue and enseignant:
            if not ue.enseignants.filter(id=enseignant.id).exists():
                raise serializers.ValidationError({
                    'enseignant': "Cet enseignant n'est pas assigné à cette unité d'enseignement."
                })

        return attrs

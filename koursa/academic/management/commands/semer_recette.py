"""
Peuple une base d'essai avec un jeu de donnees realiste.

Les tests de bout en bout ont besoin d'un systeme deja configure : une annee
ouverte, une structure academique, des cours, des comptes de chaque role. Les
construire depuis l'interface a chaque execution serait long et fragile.

Cette commande ne doit JAMAIS viser la production : elle refuse de s'executer
si la base contient deja des fiches de suivi, signe d'un systeme en service.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from academic.models import (
    AnneeAcademique, Departement, Faculte, Filiere, MandatDelegue, Niveau,
    Salle, Semestre, StatutMandat,
)
from teaching.models import FicheSuivi, UniteEnseignement
from users.models import EmailWhitelist, Role, StatutCompte

Utilisateur = get_user_model()

MOT_DE_PASSE = 'Recette2026!'


class Command(BaseCommand):
    help = "Peuple une base d'essai pour les tests de bout en bout."

    def add_arguments(self, parseur):
        parseur.add_argument(
            '--forcer', action='store_true',
            help="Peupler meme si des fiches existent deja (jamais en production).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if FicheSuivi.objects.exists() and not options['forcer']:
            raise CommandError(
                "Cette base contient deja des fiches de suivi : elle ressemble a "
                "un systeme en service. Refus d'ecrire. Utilisez --forcer si vous "
                "etes certain qu'il s'agit d'une base d'essai."
            )

        roles = {nom: Role.objects.get_or_create(nom_role=nom)[0] for nom in (
            Role.SUPER_ADMIN, Role.CHEF_DEPARTEMENT, Role.ENSEIGNANT, Role.DELEGUE,
        )}

        # --- Structure academique -----------------------------------------
        faculte, _ = Faculte.objects.get_or_create(nom_faculte='Faculte des Sciences')
        departement, _ = Departement.objects.get_or_create(
            nom_departement='Informatique', faculte=faculte)
        filiere_inf, _ = Filiere.objects.get_or_create(
            nom_filiere='INF', departement=departement)
        filiere_ict, _ = Filiere.objects.get_or_create(
            nom_filiere='ICT4D', departement=departement)

        niveaux = {}
        for filiere in (filiere_inf, filiere_ict):
            for nom in ('L1', 'L2', 'L3', 'M1', 'M2'):
                niveau, _ = Niveau.objects.get_or_create(nom_niveau=nom, filiere=filiere)
                niveaux[(filiere.nom_filiere, nom)] = niveau

        for numero in range(1, 13):
            Salle.objects.get_or_create(nom_salle='A%03d' % (100 + numero))

        # --- Annee et semestres --------------------------------------------
        annee, _ = AnneeAcademique.objects.get_or_create(
            libelle='2026-2027',
            defaults={'est_active': True, 'est_configuree': True},
        )
        AnneeAcademique.objects.exclude(pk=annee.pk).update(est_active=False)
        annee.est_active = True
        annee.est_configuree = True
        annee.save()

        semestres = {}
        for numero, (debut, fin) in enumerate(
            [(date(2026, 10, 1), date(2027, 2, 28)), (date(2027, 3, 1), date(2027, 7, 31))],
            start=1,
        ):
            semestre, _ = Semestre.objects.get_or_create(
                annee_academique=annee, numero=numero,
                defaults={'est_actif': numero == 1, 'date_debut': debut, 'date_fin': fin},
            )
            semestres[numero] = semestre

        # --- Comptes --------------------------------------------------------
        def compte(email, prenom, nom, role, **extra):
            utilisateur, cree = Utilisateur.objects.get_or_create(
                email=email,
                defaults={'first_name': prenom, 'last_name': nom,
                          'statut': StatutCompte.ACTIF, **extra},
            )
            if cree:
                utilisateur.set_password(MOT_DE_PASSE)
                utilisateur.save()
            utilisateur.roles.add(roles[role])
            return utilisateur

        admin = compte('admin@recette.test', 'Ada', 'Admin', Role.SUPER_ADMIN,
                       is_staff=True, is_superuser=True)
        chef = compte('chef@recette.test', 'Charles', 'Chef', Role.CHEF_DEPARTEMENT)
        departement.chef_departement = chef
        departement.save()

        enseignants = [
            compte('enseignant%d@recette.test' % i, 'Eva%d' % i, 'Enseignant',
                   Role.ENSEIGNANT)
            for i in range(1, 4)
        ]
        for enseignant in enseignants:
            EmailWhitelist.objects.get_or_create(
                email=enseignant.email,
                defaults={'role_type': 'ENSEIGNANT', 'departement': departement},
            )

        # Un delegue au mandat approuve, un autre qui doit encore le declarer :
        # les deux situations doivent etre testables sans manipulation.
        delegue = compte('delegue@recette.test', 'Dina', 'Deleguee', Role.DELEGUE,
                         niveau_represente=niveaux[('INF', 'M2')])
        MandatDelegue.objects.get_or_create(
            utilisateur=delegue, annee_academique=annee,
            defaults={'niveau': niveaux[('INF', 'M2')], 'statut': StatutMandat.APPROUVE},
        )
        compte('delegue.nouveau@recette.test', 'Noe', 'Nouveau', Role.DELEGUE)

        compte('attente@recette.test', 'Paul', 'Attente', Role.ENSEIGNANT,
               statut=StatutCompte.EN_ATTENTE)

        # --- Unites d'enseignement -------------------------------------------
        cours = 0
        for filiere in (filiere_inf, filiere_ict):
            prefixe = 'INF' if filiere is filiere_inf else 'ICT'
            for rang, nom_niveau in enumerate(('L1', 'L2', 'L3', 'M1', 'M2'), start=1):
                for indice in range(1, 4):
                    for numero, semestre in semestres.items():
                        code = '%s%d%d%d' % (prefixe, rang, numero, indice)
                        ue, cree = UniteEnseignement.objects.get_or_create(
                            code_ue=code, semestre_obj=semestre,
                            defaults={'libelle_ue': 'Cours %s' % code, 'semestre': numero},
                        )
                        ue.niveaux.add(niveaux[(filiere.nom_filiere, nom_niveau)])
                        ue.enseignants.add(enseignants[indice % len(enseignants)])
                        cours += 1 if cree else 0

        self.stdout.write(self.style.SUCCESS(
            "Base d'essai peuplee : %d cours, %d salles, %d comptes."
            % (UniteEnseignement.objects.count(), Salle.objects.count(),
               Utilisateur.objects.count())
        ))
        self.stdout.write("Mot de passe de tous les comptes : %s" % MOT_DE_PASSE)
        self.stdout.write("  super admin   admin@recette.test")
        self.stdout.write("  chef          chef@recette.test")
        self.stdout.write("  enseignant    enseignant1@recette.test")
        self.stdout.write("  delegue       delegue@recette.test  (classe validee)")
        self.stdout.write("  delegue       delegue.nouveau@recette.test  (classe a declarer)")
        _ = admin

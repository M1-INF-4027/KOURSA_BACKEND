from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from users.permissions import IsHoD
from teaching.models import FicheSuivi, StatutFiche
from academic.models import Departement
from users.models import Utilisateur, Role
from django.db.models import Sum
from datetime import datetime, timedelta
from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment

class DashboardStatsView(APIView):
    permission_classes = [IsAuthenticated, IsHoD]

    def get(self, request, *args, **kwargs):
        hod = request.user

        try:
            departement = Departement.objects.get(chef_departement=hod)
        except Departement.DoesNotExist:
            return Response(
                {"detail": "Vous avez le rôle de Chef de Département, mais vous n'êtes assigné à aucun département."}, 
                status=403 
            )


        current_month = datetime.now().month
        current_year = datetime.now().year
        
        heures_validees_mois = FicheSuivi.objects.filter(
            ue__niveaux__filiere__departement=departement,
            statut=StatutFiche.VALIDEE,
            date_cours__year=current_year,
            date_cours__month=current_month
        ).aggregate(total_heures=Sum('duree'))['total_heures'] or timedelta(0)

        cutoff_date = datetime.now() - timedelta(days=2)
        fiches_en_retard = FicheSuivi.objects.filter(
            ue__niveaux__filiere__departement=departement,
            statut=StatutFiche.SOUMISE,
            date_soumission__lt=cutoff_date
        ).count()
        
        heures_par_ue = FicheSuivi.objects.filter(
            ue__niveaux__filiere__departement=departement,
            statut=StatutFiche.VALIDEE,
            date_cours__year=current_year,
            date_cours__month=current_month
        ).values('ue__code_ue', 'ue__libelle_ue').annotate(
            total_duree=Sum('duree')
        ).order_by('-total_duree')

        data = {
            'heures_validees_ce_mois': round(heures_validees_mois.total_seconds() / 3600, 2),
            'fiches_en_retard_de_validation': fiches_en_retard,
            'repartition_heures_par_ue_ce_mois': [
                {
                    'code_ue': item['ue__code_ue'],
                    'libelle_ue': item['ue__libelle_ue'],
                    'heures_effectuees': round(item['total_duree'].total_seconds() / 3600, 2)
                } for item in heures_par_ue
            ]
        }
        
        return Response(data)
    
class ExportHeuresView(APIView):
    permission_classes = [IsAuthenticated, IsHoD]

    def get(self, request, *args, **kwargs):
        hod = request.user
        try:
            departement = Departement.objects.get(chef_departement=hod)
        except Departement.DoesNotExist:
            return Response({"detail": "Vous n'êtes assigné à aucun département."}, status=403)

        try:
            year = int(request.query_params.get('annee', datetime.now().year))
            month = int(request.query_params.get('mois', datetime.now().month))
        except (ValueError, TypeError):
            return Response({"detail": "Les paramètres 'annee' et 'mois' doivent être des nombres valides."}, status=400)

        heures_par_enseignant = FicheSuivi.objects.filter(
            ue__niveaux__filiere__departement=departement,
            statut=StatutFiche.VALIDEE,
            date_cours__year=year,
            date_cours__month=month
        ).values(
            'enseignant__id', 
            'enseignant__first_name', 
            'enseignant__last_name'
        ).annotate(
            total_duree=Sum('duree')
        ).order_by('enseignant__last_name')

        wb = Workbook()
        ws = wb.active
        ws.title = f"Heures {month:02d}-{year}"

        headers = ["Nom", "Prénom", "Heures Effectuées"]
        ws.append(headers)
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')

        for item in heures_par_enseignant:
            heures = round(item['total_duree'].total_seconds() / 3600, 2) if item['total_duree'] else 0
            row = [
                item['enseignant__last_name'],
                item['enseignant__first_name'],
                heures
            ]
            ws.append(row)
        
        for col in ['A', 'B', 'C']:
            ws.column_dimensions[col].autosize = True

        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        filename = f"export_heures_{departement.nom_departement.lower()}_{month:02d}_{year}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        wb.save(response)
        
        return response
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import Utilisateur


class UtilisateurCreationForm(UserCreationForm):
    class Meta:
        model = Utilisateur
        fields = ('email', 'first_name', 'last_name')


class UtilisateurChangeForm(UserChangeForm):
    class Meta:
        model = Utilisateur
        fields = ('email', 'first_name', 'last_name')

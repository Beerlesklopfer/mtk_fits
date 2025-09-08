from django.urls import path
from . import views
import utils.sheets as sheet_names

app_name = 'fits'


urlpatterns = [
    path('', views.FitsView.as_view(), name='index'),
    path('rpc/', views.FitsRPCView.as_view(), name='tab_switching'),
]

# Add dynamic URL patterns for each tab-sheet name
for name in sheet_names.sheet_names:
    urlpatterns.append(path(f'rpc/{name}', views.FitsRPCView.as_view(), name=f'tab_{name}'))

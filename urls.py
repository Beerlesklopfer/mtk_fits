from django.urls import path
from . import views
import main.sheets as sheet_names

app_name = 'fits'


urlpatterns = [
    path('', views.FitsRPCView.as_view(), name='index'),
    path('calculation/image/', views.FitsRPCView.as_view(), name='tab_calculation_system_selection'),
    path('calculation/image/', views.FitsRPCView.as_view(), name='tab_calculation_image'),
    path('calculation/s_max/', views.FitsRPCView.as_view(), name='tab_calculation_s_max'),
    path('calculation/s_min/', views.FitsRPCView.as_view(), name='tab_calculation_s_min'),
    path('calculation/fit_type/', views.FitsRPCView.as_view(), name='tab_calculation_fit_type'),
    path('calculation/fit_system/', views.FitsRPCView.as_view(), name='tab_calculation_fit_system'),
    # path('rpc/', views.FitsRPCView.as_view(), name='tab_switching'),
    # path('rpc/bore/tolerance/<str:tolerance>/', views.FitsRPCView.as_view(), name='bore_tolerance'),
    # path('rpc/bore/deviation/<str:deviation>/', views.FitsRPCView.as_view(), name='bore_deviation'),
]

# Add dynamic URL patterns for each tab-sheet name
for name in sheet_names.sheet_names:
    urlpatterns.append(path(f'rpc/{name}', views.FitsRPCView.as_view(), name=f'tab_{name}'))

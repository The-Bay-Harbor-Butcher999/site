from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.enrollment_list, name='enrollment_list'),
    path('enrollments/new/', views.enrollment_create, name='enrollment_create'),
    path('enrollments/<int:pk>/', views.enrollment_detail, name='enrollment_detail'),
    path('enrollments/<int:pk>/status/', views.enrollment_change_status, name='enrollment_change_status'),
    path('enrollments/<int:pk>/comment/', views.enrollment_add_comment, name='enrollment_add_comment'),
    path('enrollments/<int:pk>/delete/', views.enrollment_delete, name='enrollment_delete'),
    path('schedule/', views.schedule_view, name='schedule'),
    path('directories/', views.directories_view, name='directories'),
    path('users/', views.users_view, name='users'),
    path('reports/', views.report_view, name='reports'),
    path('reports/export/csv/', views.export_csv, name='export_csv'),
    path('reports/export/excel/', views.export_excel, name='export_excel'),
]

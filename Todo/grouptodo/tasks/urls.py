from django.urls import path
from . import views # Import views from the current app (tasks)

# --- FIX: Define the namespace for this app ---
app_name = 'tasks'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # --- Group URLs ---
    path('group/create/', views.GroupCreateView.as_view(), name='group_create'),
    path('group/<int:pk>/', views.GroupDetailView.as_view(), name='group_detail'),
    path('group/<int:pk>/update/', views.GroupUpdateView.as_view(), name='group_update'),
    path('group/<int:pk>/delete/', views.GroupDeleteView.as_view(), name='group_delete'),

    # --- Member URLs ---
    path('group/<int:group_pk>/add_member/', views.add_member, name='add_member'),
    path('group/<int:group_pk>/remove_member/<int:user_pk>/', views.remove_member, name='remove_member'),
    path('group/<int:group_pk>/leave/', views.leave_group, name='leave_group'),
    
    # --- Pledge URL ---
    path('group/<int:group_pk>/pledge/', views.create_pledge, name='create_pledge'),
    path('group/<int:group_pk>/payout/', views.process_weekly_payout, name='process_payout'),

    # --- Task URLs ---
    # *** FIX: Changed parameter name to group_pk to match views.py ***
    path('group/<int:group_pk>/task/create/', views.TaskCreateView.as_view(), name='task_create'),
    path('task/<int:pk>/update/', views.TaskUpdateView.as_view(), name='task_update'),
    path('task/<int:pk>/delete/', views.TaskDeleteView.as_view(), name='task_delete'),
    path('task/<int:pk>/toggle/', views.toggle_task_complete, name='toggle_task_complete'),
    
    # --- Task Submission & Review URLs ---
    path('task/<int:task_pk>/submit/', views.TaskSubmissionCreateView.as_view(), name='task_submit_proof'),
    path('submission/<int:submission_pk>/', views.view_submission, name='view_submission'),
    path('submission/<int:submission_pk>/review/', views.review_submission, name='review_submission'),
]


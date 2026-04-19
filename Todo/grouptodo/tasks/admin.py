from django.contrib import admin
# --- UPDATED: Import Badge ---
from .models import Group, Task, Profile, WeeklyPledge, Badge, TaskSubmission

# Register your models here.

# Customize Profile display in admin to show points/coins
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'coins', 'points', 'current_streak', 'longest_streak')
    search_fields = ('user__username',)

# Customize Task display
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'group', 'status', 'assigned_to', 'due_date', 'requires_proof')
    list_filter = ('status', 'group', 'requires_proof')
    search_fields = ('title', 'description')

# Customize Group display
class GroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'created_at')
    search_fields = ('name', 'owner__username')
    filter_horizontal = ('members',) # Makes M2M field easier to use

# Customize Badge display
class BadgeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'icon_class')
    search_fields = ('name',)

# Customize Submission display
class TaskSubmissionAdmin(admin.ModelAdmin):
    list_display = ('task', 'submitted_by', 'status', 'reviewed_by')
    # --- FIX: Removed 'status' from list_filter, as it's a method, not a field ---
    list_filter = ('task__group', 'is_approved')
    search_fields = ('task__title', 'submitted_by__username')
    
    def status(self, obj):
        if obj.is_approved:
            return "Approved"
        if obj.reviewed_by:
            return "Needs Revision"
        if obj.pk: # check if it's saved
            return "Pending Review"
        return "N/A"


# Unregister old basic registrations if they exist, then register with custom admin
admin.site.unregister(Group) if admin.site.is_registered(Group) else None
admin.site.register(Group, GroupAdmin)

admin.site.unregister(Task) if admin.site.is_registered(Task) else None
admin.site.register(Task, TaskAdmin)

admin.site.unregister(Profile) if admin.site.is_registered(Profile) else None
admin.site.register(Profile, ProfileAdmin)

admin.site.unregister(WeeklyPledge) if admin.site.is_registered(WeeklyPledge) else None
admin.site.register(WeeklyPledge)

# --- NEW: Register Badge and TaskSubmission ---
admin.site.register(Badge, BadgeAdmin)
admin.site.register(TaskSubmission, TaskSubmissionAdmin)


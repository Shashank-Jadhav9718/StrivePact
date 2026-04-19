from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import date, timedelta # Import timedelta

# --- Group Model Definition ---
class Group(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    owner = models.ForeignKey(
        User,
        related_name='owned_groups',
        on_delete=models.CASCADE
    )
    members = models.ManyToManyField(
        User,
        related_name='task_groups'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

# --- Task Model Definition ---
class Task(models.Model):
    STATUS_OPEN = 'open'
    STATUS_PENDING_REVIEW = 'pending'
    STATUS_NEEDS_REVISION = 'revision'
    STATUS_COMPLETE = 'complete'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_PENDING_REVIEW, 'Pending Review'),
        (STATUS_NEEDS_REVISION, 'Needs Revision'),
        (STATUS_COMPLETE, 'Completed'),
    ]
    group = models.ForeignKey(
        Group,
        related_name='tasks',
        on_delete=models.CASCADE
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    assigned_to = models.ForeignKey(
        User,
        related_name='assigned_tasks',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    creator = models.ForeignKey(
        User,
        related_name='created_tasks',
        on_delete=models.CASCADE
    )
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN
    )
    requires_proof = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        if self.due_date and self.status != self.STATUS_COMPLETE:
            return self.due_date < timezone.now().date()
        return False
    
    @property
    def is_complete(self):
        return self.status == self.STATUS_COMPLETE

# --- NEW: Badge Model ---
class Badge(models.Model):
    """Defines an achievement badge."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    icon_class = models.CharField(max_length=50, help_text="e.g., 'bi-star-fill'") # Bootstrap icon class
    
    def __str__(self):
        return self.name

# --- Profile Model (Updated for Badges) ---
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    coins = models.IntegerField(default=100)
    points = models.IntegerField(default=0)
    current_streak = models.IntegerField(default=0)
    longest_streak = models.IntegerField(default=0)
    last_completion_date = models.DateField(null=True, blank=True)
    
    # --- NEW: Badges Field ---
    badges = models.ManyToManyField(Badge, blank=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

    def update_streak(self):
        """Updates the user's streak based on today's date."""
        today = timezone.now().date()
        if self.last_completion_date == today:
            return
        yesterday = today - timedelta(days=1)
        if self.last_completion_date == yesterday:
            self.current_streak += 1
        else:
            self.current_streak = 1
        if self.current_streak > self.longest_streak:
            self.longest_streak = self.current_streak
        self.last_completion_date = today
        self.save()

# --- Signal to auto-create Profile ---
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()

# --- Weekly Pledge Model ---
class WeeklyPledge(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    week_start_date = models.DateField()
    amount = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ('user', 'group', 'week_start_date')
    def __str__(self):
        return f"{self.user.username}'s {self.amount} coin pledge for {self.group.name} (Week of {self.week_start_date})"

# --- Task Submission Model ---
class TaskSubmission(models.Model):
    task = models.ForeignKey(Task, related_name='submissions', on_delete=models.CASCADE)
    submitted_by = models.ForeignKey(User, related_name='submissions', on_delete=models.CASCADE)
    proof_text = models.TextField(blank=True, null=True)
    proof_link = models.URLField(blank=True, null=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_approved = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(User, related_name='reviews_given', on_delete=models.SET_NULL, null=True, blank=True)
    review_comment = models.TextField(blank=True, null=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    def __str__(self):
        return f"Submission for '{self.task.title}' by {self.submitted_by.username}"


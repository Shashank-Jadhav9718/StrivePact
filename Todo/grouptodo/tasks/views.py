from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import CreateView, UpdateView, DeleteView, DetailView, ListView
from django.http import HttpResponseForbidden, Http404, HttpResponseRedirect, JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.auth.models import User
from django.db import models
from datetime import date, timedelta
from django.utils import timezone
from django.db import transaction

# Import forms and models
from .forms import (
    UserRegistrationForm, GroupForm, TaskForm, AddMemberForm,
    PledgeForm, TaskSubmissionForm, SubmissionReviewForm
)
from .models import Group, Task, Profile, WeeklyPledge, TaskSubmission, Badge

# --- Constants for Points ---
POINTS_FOR_SIMPLE_TASK = 5
POINTS_FOR_PROOF_TASK = 10
POINTS_FOR_REVIEW = 3

# --- Badge Awarding Logic ---
@transaction.atomic
def check_and_award_badges(user, is_review=False):
    """Checks a user's accomplishments and awards new badges."""
    try:
        profile = user.profile
    except Profile.DoesNotExist:
        profile = Profile.objects.create(user=user)

    # 1. "First Task" Badge
    try:
        badge = Badge.objects.get(name="First Task")
        if not profile.badges.filter(name="First Task").exists():
            completed_tasks_count = Task.objects.filter(
                models.Q(assigned_to=user) | models.Q(creator=user),
                status=Task.STATUS_COMPLETE
            ).count()
            
            if completed_tasks_count >= 1:
                profile.badges.add(badge)
    except Badge.DoesNotExist:
        pass

    # 2. "Reviewer" Badge
    if is_review:
        try:
            badge = Badge.objects.get(name="Reviewer")
            if not profile.badges.filter(name="Reviewer").exists():
                review_count = TaskSubmission.objects.filter(reviewed_by=user).count()
                if review_count >= 1:
                    profile.badges.add(badge)
        except Badge.DoesNotExist:
            pass

    # 3. "Streak Starter" Badge
    try:
        badge = Badge.objects.get(name="Streak Starter")
        if not profile.badges.filter(name="Streak Starter").exists():
            if profile.current_streak >= 3:
                profile.badges.add(badge)
    except Badge.DoesNotExist:
        pass


# --- Registration View ---
def register(request):
    """Handles user registration."""
    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            return redirect('login')
    else:
        form = UserRegistrationForm()
    context = {'form': form}
    return render(request, 'registration/register.html', context)


# --- Dashboard View ---
@login_required
def dashboard(request):
    """Displays the user's dashboard with their groups and filtered assigned tasks."""
    user = request.user
    if not hasattr(user, 'profile'):
        Profile.objects.create(user=user)
        
    user_groups = Group.objects.filter(members=user).order_by('name')
    status_filter = request.GET.get('status', 'open')
    
    assigned_tasks_queryset = Task.objects.filter(
        assigned_to=user,
        group__in=user_groups
    )

    if status_filter == 'open':
        assigned_tasks_queryset = assigned_tasks_queryset.exclude(status=Task.STATUS_COMPLETE)
    elif status_filter == 'completed':
        assigned_tasks_queryset = assigned_tasks_queryset.filter(status=Task.STATUS_COMPLETE)

    if status_filter == 'completed':
         assigned_tasks_queryset = assigned_tasks_queryset.order_by('-updated_at')
    else:
        assigned_tasks_queryset = assigned_tasks_queryset.order_by(models.F('due_date').asc(nulls_last=True), 'created_at')

    user_badges = user.profile.badges.all()

    context = {
        'groups': user_groups,
        'assigned_tasks': assigned_tasks_queryset,
        'current_status_filter': status_filter,
        'user_badges': user_badges,
    }
    return render(request, 'tasks/dashboard.html', context)

# --- Group CRUD Views ---
class GroupCreateView(LoginRequiredMixin, CreateView):
    model = Group
    form_class = GroupForm
    template_name = 'tasks/group_form.html'
    success_url = reverse_lazy('tasks:dashboard')
    def form_valid(self, form):
        form.instance.owner = self.request.user
        response = super().form_valid(form)
        self.object.members.add(self.request.user)
        return response
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_creating'] = True
        return context

class GroupDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Group
    template_name = 'tasks/group_detail.html'
    context_object_name = 'group'
    def test_func(self):
        group = self.get_object()
        return group.members.filter(pk=self.request.user.pk).exists()
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        group = self.get_object()
        status_filter = self.request.GET.get('status', 'all')
        assignee_filter = self.request.GET.get('assignee', 'all')
        sort_by = self.request.GET.get('sort', 'created')
        sort_dir = self.request.GET.get('dir', 'desc')
        tasks_queryset = group.tasks.all()
        
        if status_filter == 'open':
            tasks_queryset = tasks_queryset.exclude(status=Task.STATUS_COMPLETE)
        elif status_filter == 'completed':
            tasks_queryset = tasks_queryset.filter(status=Task.STATUS_COMPLETE)
            
        context['current_status_filter'] = status_filter
        if assignee_filter == 'me':
            tasks_queryset = tasks_queryset.filter(assigned_to=self.request.user)
        context['current_assignee_filter'] = assignee_filter
        
        order_field = '-created_at'
        if sort_by == 'due':
            if sort_dir == 'asc':
                order_field = models.F('due_date').asc(nulls_last=True)
            else:
                order_field = models.F('due_date').desc(nulls_first=True)
        elif sort_by == 'created':
            if sort_dir == 'asc':
                order_field = 'created_at'
            else:
                order_field = '-created_at'
        
        tasks_queryset = tasks_queryset.order_by(
            models.Case(
                models.When(status=Task.STATUS_COMPLETE, then=4),
                models.When(status=Task.STATUS_PENDING_REVIEW, then=3),
                models.When(status=Task.STATUS_NEEDS_REVISION, then=2),
                models.When(status=Task.STATUS_OPEN, then=1),
                default=5
            ),
            order_field, 
            'pk'
        )
        
        context['tasks'] = tasks_queryset
        context['current_sort_by'] = sort_by
        context['current_sort_dir'] = sort_dir
        context['is_owner'] = (self.request.user == group.owner)
        context['is_member_only'] = (self.request.user in group.members.all() and self.request.user != group.owner)
        
        members = group.members.select_related('profile').all()
        context['members'] = members.order_by('username')
        context['leaderboard'] = members.order_by('-profile__points') 

        today = timezone.now().date()
        week_start_date = today - timezone.timedelta(days=today.weekday())
        context['has_pledged'] = WeeklyPledge.objects.filter(
            user=self.request.user,
            group=group,
            week_start_date=week_start_date
        ).exists()

        context['can_process_payout'] = (self.request.user == group.owner)

        return context

class GroupUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Group
    form_class = GroupForm
    template_name = 'tasks/group_form.html'
    def test_func(self):
        group = self.get_object()
        return self.request.user == group.owner
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_creating'] = False
        return context
    def get_success_url(self):
        return reverse_lazy('tasks:group_detail', kwargs={'pk': self.object.pk})

class GroupDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Group
    template_name = 'tasks/group_confirm_delete.html'
    success_url = reverse_lazy('tasks:dashboard')
    context_object_name = 'group'
    def test_func(self):
        group = self.get_object()
        return self.request.user == group.owner

# --- Task CRUD Views ---
class TaskCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Task
    form_class = TaskForm
    template_name = 'tasks/task_form.html'
    def test_func(self):
        group = get_object_or_404(Group, pk=self.kwargs['group_pk'])
        return group.members.filter(pk=self.request.user.pk).exists()
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        group = get_object_or_404(Group, pk=self.kwargs['group_pk'])
        kwargs['group'] = group
        return kwargs
    def form_valid(self, form):
        group = get_object_or_404(Group, pk=self.kwargs['group_pk'])
        form.instance.group = group
        form.instance.creator = self.request.user
        return super().form_valid(form)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['group'] = get_object_or_404(Group, pk=self.kwargs['group_pk'])
        context['is_creating'] = True
        return context
    def get_success_url(self):
        return reverse('tasks:group_detail', kwargs={'pk': self.kwargs['group_pk']})

class TaskUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Task
    form_class = TaskForm
    template_name = 'tasks/task_form.html'
    context_object_name = 'task'
    def test_func(self):
        task = self.get_object()
        user_is_member = task.group.members.filter(pk=self.request.user.pk).exists()
        return user_is_member
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['group'] = self.object.group
        return kwargs
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['group'] = self.object.group
        context['is_creating'] = False
        return context
    def get_success_url(self):
        return reverse('tasks:group_detail', kwargs={'pk': self.object.group.pk})

class TaskDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Task
    template_name = 'tasks/task_confirm_delete.html'
    context_object_name = 'task'
    def test_func(self):
        task = self.get_object()
        user_is_member = task.group.members.filter(pk=self.request.user.pk).exists()
        user_can_delete = (self.request.user == task.group.owner or self.request.user == task.creator)
        return user_is_member and user_can_delete
    def get_success_url(self):
        return reverse('tasks:group_detail', kwargs={'pk': self.object.group.pk})

# --- Toggle Task Complete View (Updated for Badges) ---
@login_required
@require_POST
@transaction.atomic
def toggle_task_complete(request, pk):
    task = get_object_or_404(Task, pk=pk)
    
    if not task.group.members.filter(pk=request.user.pk).exists():
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
             return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        return HttpResponseForbidden("You are not allowed to modify tasks in this group.")

    user_to_reward = task.assigned_to or task.creator
    if not hasattr(user_to_reward, 'profile'):
        Profile.objects.create(user=user_to_reward)

    if task.requires_proof and task.status != Task.STATUS_COMPLETE:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
             return JsonResponse({'success': False, 'error': 'Task requires proof, cannot toggle complete.'}, status=400)
        messages.error(request, "This task requires proof of work and cannot be toggled directly.")
        return HttpResponseRedirect(reverse('tasks:group_detail', kwargs={'pk': task.group.pk}))

    new_status_is_complete = False
    ajax_message = ""
    
    if task.status == Task.STATUS_COMPLETE:
        task.status = Task.STATUS_OPEN
        new_status_is_complete = False
        point_change = 0
        if not task.requires_proof:
            point_change = POINTS_FOR_SIMPLE_TASK
        else:
            point_change = POINTS_FOR_PROOF_TASK
            submission = task.submissions.filter(is_approved=True).first()
            if submission and submission.reviewed_by:
                if not hasattr(submission.reviewed_by, 'profile'): Profile.objects.create(user=submission.reviewed_by)
                submission.reviewed_by.profile.points = max(0, submission.reviewed_by.profile.points - POINTS_FOR_REVIEW)
                submission.reviewed_by.profile.save()
                submission.is_approved = False
                submission.reviewed_by = None
                submission.review_comment = "Task reverted to open."
                submission.save()
        user_to_reward.profile.points = max(0, user_to_reward.profile.points - point_change)
        user_to_reward.profile.save()
        ajax_message = f"Task marked as open. {point_change} points deducted."
        messages.info(request, ajax_message)
    
    else: 
        task.status = Task.STATUS_COMPLETE
        new_status_is_complete = True
        if not task.requires_proof:
            user_to_reward.profile.points += POINTS_FOR_SIMPLE_TASK
            user_to_reward.profile.save()
            user_to_reward.profile.update_streak()
            check_and_award_badges(user_to_reward)
            ajax_message = f"Task completed! {user_to_reward.username} earned {POINTS_FOR_SIMPLE_TASK} points."
            messages.success(request, ajax_message)
    
    task.save()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'is_complete': new_status_is_complete,
            'task_id': task.pk,
            'points_message': ajax_message
        })
    else:
        return HttpResponseRedirect(reverse('tasks:group_detail', kwargs={'pk': task.group.pk}))

# --- Task Submission Views ---
class TaskSubmissionCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = TaskSubmission
    form_class = TaskSubmissionForm
    template_name = 'tasks/submit_proof.html'

    def test_func(self):
        task = get_object_or_404(Task, pk=self.kwargs['task_pk'])
        return task.group.members.filter(pk=self.request.user.pk).exists()
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['task'] = get_object_or_404(Task, pk=self.kwargs['task_pk'])
        return context
    def form_valid(self, form):
        task = get_object_or_404(Task, pk=self.kwargs['task_pk'])
        form.instance.task = task
        form.instance.submitted_by = self.request.user
        task.status = Task.STATUS_PENDING_REVIEW
        task.save()
        messages.success(self.request, f"Proof submitted for '{task.title}'. It is now pending review.")
        return super().form_valid(form)
    def get_success_url(self):
        return reverse('tasks:group_detail', kwargs={'pk': self.object.task.group.pk})

@login_required
def view_submission(request, submission_pk):
    """Display a single task submission and allow peers to review it."""
    submission = get_object_or_404(
        TaskSubmission.objects.select_related('task', 'task__group', 'submitted_by', 'reviewed_by'),
        pk=submission_pk
    )
    task = submission.task
    group = task.group
    user = request.user

    if not group.members.filter(pk=user.pk).exists():
        messages.error(request, "You are not a member of this group.")
        return redirect('tasks:dashboard')
        
    can_review = (user != submission.submitted_by)
    already_reviewed = (submission.reviewed_by is not None)

    form = SubmissionReviewForm()
    if already_reviewed:
        form = SubmissionReviewForm(instance=submission) # Show existing comment

    context = {
        'submission': submission,
        'task': task,
        'group': group,
        'form': form,
        'can_review': can_review,
        'already_reviewed': already_reviewed,
    }
    return render(request, 'tasks/submission_review.html', context)

@login_required
@require_POST
@transaction.atomic
def review_submission(request, submission_pk):
    submission = get_object_or_404(TaskSubmission.objects.select_related('task', 'task__group', 'submitted_by'), pk=submission_pk)
    task = submission.task
    group = task.group
    user = request.user
    submitter = submission.submitted_by

    if not hasattr(submitter, 'profile'): Profile.objects.create(user=submitter)
    if not hasattr(user, 'profile'): Profile.objects.create(user=user)

    if not group.members.filter(pk=user.pk).exists():
        return HttpResponseForbidden("You are not a member of this group.")
    if user == submission.submitted_by:
        messages.error(request, "You cannot review your own submission.")
        return redirect('tasks:group_detail', pk=group.pk)
    if submission.reviewed_by is not None:
        messages.warning(request, "This submission has already been reviewed.")
        return redirect('tasks:view_submission', submission_pk=submission.pk)

    form = SubmissionReviewForm(request.POST)
    
    if 'approve' in request.POST:
        if form.is_valid():
            submission.is_approved = True
            submission.reviewed_by = user
            submission.review_comment = form.cleaned_data['review_comment']
            submission.reviewed_at = timezone.now()
            submission.save()
            task.status = Task.STATUS_COMPLETE
            task.save()
            
            submitter.profile.points += POINTS_FOR_PROOF_TASK
            submitter.profile.save()
            user.profile.points += POINTS_FOR_REVIEW
            user.profile.save()
            
            submitter.profile.update_streak()
            check_and_award_badges(submitter)
            check_and_award_badges(user, is_review=True)
            
            messages.success(request, f"You approved the submission for '{task.title}'. {submitter.username} earned {POINTS_FOR_PROOF_TASK} points. You earned {POINTS_FOR_REVIEW} points.")
            return redirect('tasks:group_detail', pk=group.pk)

    elif 'reject' in request.POST:
        if form.is_valid():
            comment = form.cleaned_data['review_comment']
            if not comment:
                form.add_error('review_comment', 'A comment is required when marking for revision.')
            else:
                submission.is_approved = False
                submission.reviewed_by = user
                submission.review_comment = comment
                submission.reviewed_at = timezone.now()
                submission.save()
                task.status = Task.STATUS_NEEDS_REVISION
                task.save()
                
                user.profile.points += POINTS_FOR_REVIEW
                user.profile.save()
                
                check_and_award_badges(user, is_review=True)
                
                messages.warning(request, f"You marked '{task.title}' as needing revision. You earned {POINTS_FOR_REVIEW} points for the review.")
                return redirect('tasks:group_detail', pk=group.pk)

    context = {
        'submission': submission,
        'task': task,
        'group': group,
        'form': form,
        'can_review': True,
        'already_reviewed': False,
    }
    messages.error(request, "Please correct the errors below.")
    return render(request, 'tasks/submission_review.html', context)


# --- Member Management Views ---
@login_required
def add_member(request, group_pk):
    group = get_object_or_404(Group, pk=group_pk)
    if request.user != group.owner:
        messages.error(request, "Only the group owner can add members.")
        return redirect('tasks:group_detail', pk=group_pk)
    
    form = AddMemberForm() # Initialize form for GET
    if request.method == 'POST':
        form = AddMemberForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            try:
                user_to_add = User.objects.get(username=username)
                if user_to_add in group.members.all():
                     messages.warning(request, f"User '{username}' is already a member.")
                elif user_to_add == group.owner:
                     messages.warning(request, "Owner cannot be added again.")
                else:
                    group.members.add(user_to_add)
                    messages.success(request, f"User '{username}' added successfully.")
                    return redirect('tasks:add_member', group_pk=group_pk)
            except User.DoesNotExist:
                 messages.error(request, f"User '{username}' not found.")
    
    members = group.members.all().order_by('username')
    context = {'form': form, 'group': group, 'members': members}
    return render(request, 'tasks/add_member.html', context)

@login_required
def remove_member(request, group_pk, user_pk):
    group = get_object_or_404(Group, pk=group_pk)
    user_to_remove = get_object_or_404(User, pk=user_pk)
    if request.user != group.owner:
        messages.error(request, "Only the group owner can remove members.")
        return redirect('tasks:group_detail', pk=group_pk)
    if user_to_remove == group.owner:
        messages.error(request, "The group owner cannot be removed.")
    elif user_to_remove not in group.members.all():
         messages.warning(request, f"User '{user_to_remove.username}' is not a member.")
    else:
        group.members.remove(user_to_remove)
        messages.success(request, f"User '{user_to_remove.username}' removed successfully.")
    return redirect('tasks:add_member', group_pk=group_pk)

# --- Leave Group View ---
@login_required
def leave_group(request, group_pk):
    group = get_object_or_404(Group, pk=group_pk)
    user = request.user
    if not group.members.filter(pk=user.pk).exists():
        messages.error(request, "You are not a member of this group.")
        return redirect('tasks:dashboard')
    if user == group.owner:
        messages.error(request, "The group owner cannot leave the group.")
        return redirect('tasks:group_detail', pk=group_pk)
    else:
        group.members.remove(user)
        messages.success(request, f"You have left the group '{group.name}'.")
        return redirect('tasks:dashboard')

# --- Create Pledge View ---
@login_required
def create_pledge(request, group_pk):
    group = get_object_or_404(Group, pk=group_pk)
    user = request.user

    if not group.members.filter(pk=user.pk).exists():
        messages.error(request, "You must be a member to pledge to this group.")
        return redirect('tasks:dashboard')

    today = timezone.now().date()
    week_start_date = today - timezone.timedelta(days=today.weekday())

    existing_pledge = WeeklyPledge.objects.filter(
        user=user,
        group=group,
        week_start_date=week_start_date
    ).first()

    if existing_pledge:
        messages.warning(request, f"You have already pledged {existing_pledge.amount} coins for this group this week.")
        return redirect('tasks:group_detail', pk=group_pk)

    form = PledgeForm() # Initialize for GET
    if request.method == 'POST':
        form = PledgeForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            if not hasattr(user, 'profile'): Profile.objects.create(user=user)
            if user.profile.coins >= amount:
                user.profile.coins -= amount
                user.profile.save()

                pledge = form.save(commit=False)
                pledge.user = user
                pledge.group = group
                pledge.week_start_date = week_start_date
                pledge.save()

                messages.success(request, f"You successfully pledged {amount} coins to '{group.name}'!")
                return redirect('tasks:group_detail', pk=group_pk)
            else:
                messages.error(request, f"You do not have enough coins. Your balance is {user.profile.coins}.")
                form.add_error(None, "You do not have enough coins in your wallet.")

    if not hasattr(user, 'profile'): Profile.objects.create(user=user)
    context = {
        'form': form,
        'group': group,
        'profile': user.profile
    }
    return render(request, 'tasks/create_pledge.html', context)

# --- Process Payout View ---
@login_required
@require_POST
def process_weekly_payout(request, group_pk):
    group = get_object_or_404(Group, pk=group_pk)
    user = request.user
    if user != group.owner:
        messages.error(request, "Only the group owner can process payouts.")
        return redirect('tasks:group_detail', pk=group_pk)

    today = timezone.now().date()
    last_monday = today - timezone.timedelta(days=today.weekday() + 7)
    last_sunday = last_monday + timezone.timedelta(days=6)

    pledges = WeeklyPledge.objects.filter(
        group=group,
        week_start_date=last_monday
    )
    
    if not pledges.exists():
        messages.warning(request, "No pledges found for the previous week to process.")
        return redirect('tasks:group_detail', pk=group_pk)

    winners = []
    losers = []
    total_forfeited_pot = 0
    total_pledged = 0

    for pledge in pledges:
        if not hasattr(pledge.user, 'profile'):
            Profile.objects.create(user=pledge.user)

    for pledge in pledges:
        pledging_user = pledge.user
        total_pledged += pledge.amount

        tasks_for_user = Task.objects.filter(
            group=group,
            assigned_to=pledging_user,
            due_date__range=[last_monday, last_sunday]
        )
        
        all_complete = True
        if tasks_for_user.exists():
            for task in tasks_for_user:
                if not task.is_complete:
                    all_complete = False
                    break
        else:
            all_complete = True 

        if all_complete:
            winners.append(pledge)
        else:
            losers.append(pledge)
            total_forfeited_pot += pledge.amount

    payout_per_winner = 0
    if winners:
        if total_forfeited_pot > 0:
            payout_per_winner = total_forfeited_pot // len(winners)
        
        for winner_pledge in winners:
            winner_user = winner_pledge.user
            winner_user.profile.coins += winner_pledge.amount
            winner_user.profile.coins += payout_per_winner
            winner_user.profile.save()

    pledges.delete()

    messages.success(request, f"Payout processed for week of {last_monday}. Total pledged: {total_pledged} coins. Total forfeited: {total_forfeited_pot} coins. Winners: {len(winners)}. Payout per winner: {payout_per_winner} coins.")
    return redirect('tasks:group_detail', pk=group_pk)

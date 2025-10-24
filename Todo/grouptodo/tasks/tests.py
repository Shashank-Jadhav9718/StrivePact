from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Group, Task, Profile, WeeklyPledge, TaskSubmission, Badge # Import all models
# Import all forms
from .forms import (
    GroupForm, TaskForm, AddMemberForm, 
    UserRegistrationForm, PledgeForm, TaskSubmissionForm
)
from django.utils import timezone
import datetime
import json

# --- Group Model Tests ---
class GroupModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.test_user = User.objects.create_user(username='testowner', password='password123')
        cls.test_group = Group.objects.create(name='Test Group Alpha', owner=cls.test_user)
        cls.test_group.members.add(cls.test_user)
    def test_group_str_representation(self):
        self.assertEqual(str(self.test_group), self.test_group.name)
    def test_group_creation_sets_owner(self):
        self.assertEqual(self.test_group.owner, self.test_user)

# --- Task Model Tests ---
class TaskModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username='taskowner', password='password123')
        cls.assignee = User.objects.create_user(username='taskassignee', password='password123')
        cls.group = Group.objects.create(name='Task Test Group', owner=cls.owner)
        cls.group.members.add(cls.owner, cls.assignee)
        cls.task = Task.objects.create(
            group=cls.group, title='Test Task One', creator=cls.owner, assigned_to=cls.assignee, status=Task.STATUS_OPEN
        )
    def test_task_str_representation(self):
        self.assertEqual(str(self.task), self.task.title)
    def test_task_defaults(self):
        self.assertEqual(self.task.status, Task.STATUS_OPEN)
        self.assertFalse(self.task.is_complete)
    def test_task_assigns_group_and_creator(self):
        self.assertEqual(self.task.group, self.group)
        self.assertEqual(self.task.creator, self.owner)
        self.assertEqual(self.task.assigned_to, self.assignee)
    def test_is_overdue_property_no_due_date(self):
        task_no_due = Task.objects.create(group=self.group, title='No Due Date', creator=self.owner)
        self.assertFalse(task_no_due.is_overdue)
    def test_is_overdue_property_future_due_date(self):
        future_date = timezone.now().date() + datetime.timedelta(days=5)
        task_future = Task.objects.create(group=self.group, title='Future Due', creator=self.owner, due_date=future_date)
        self.assertFalse(task_future.is_overdue)
    def test_is_overdue_property_past_due_date_open(self):
        past_date = timezone.now().date() - datetime.timedelta(days=5)
        task_past_open = Task.objects.create(group=self.group, title='Past Due Open', creator=self.owner, due_date=past_date, status=Task.STATUS_OPEN)
        self.assertTrue(task_past_open.is_overdue)
    def test_is_overdue_property_past_due_date_complete(self):
        past_date = timezone.now().date() - datetime.timedelta(days=5)
        task_past_complete = Task.objects.create(group=self.group, title='Past Due Complete', creator=self.owner, due_date=past_date, status=Task.STATUS_COMPLETE)
        self.assertFalse(task_past_complete.is_overdue)
    def test_is_complete_property(self):
        self.task.status = Task.STATUS_OPEN
        self.assertFalse(self.task.is_complete)
        self.task.status = Task.STATUS_PENDING_REVIEW
        self.assertFalse(self.task.is_complete)
        self.task.status = Task.STATUS_NEEDS_REVISION
        self.assertFalse(self.task.is_complete)
        self.task.status = Task.STATUS_COMPLETE
        self.assertTrue(self.task.is_complete)

# --- Profile Model & Signal Tests ---
class ProfileModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='profileuser', password='password123')
    
    def test_profile_created_on_user_signal(self):
        self.assertTrue(hasattr(self.user, 'profile'))
        self.assertEqual(self.user.profile.coins, 100)
        self.assertEqual(self.user.profile.points, 0)
        self.assertEqual(self.user.profile.current_streak, 0)

    def test_profile_str_representation(self):
        self.assertEqual(str(self.user.profile), "profileuser's Profile")
        
    def test_streak_logic(self):
        profile = self.user.profile
        today = timezone.now().date()
        yesterday = today - datetime.timedelta(days=1)
        two_days_ago = today - datetime.timedelta(days=2)
        
        profile.update_streak()
        self.assertEqual(profile.current_streak, 1)
        self.assertEqual(profile.longest_streak, 1)
        self.assertEqual(profile.last_completion_date, today)
        
        profile.update_streak()
        self.assertEqual(profile.current_streak, 1)
        
        profile.last_completion_date = yesterday
        profile.save()
        profile.update_streak()
        self.assertEqual(profile.current_streak, 2)
        self.assertEqual(profile.longest_streak, 2)
        
        profile.current_streak = 5
        profile.longest_streak = 5
        profile.last_completion_date = two_days_ago
        profile.save()
        profile.update_streak()
        self.assertEqual(profile.current_streak, 1)
        self.assertEqual(profile.longest_streak, 5)

# --- Core View Tests ---
class CoreViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.test_user = User.objects.create_user(username='viewtester', password='password123')
    def setUp(self):
        self.client = Client()

    def test_dashboard_requires_login(self):
        dashboard_url = reverse('tasks:dashboard')
        login_url = reverse('login')
        response = self.client.get(dashboard_url)
        self.assertRedirects(response, f'{login_url}?next={dashboard_url}')
    def test_dashboard_accessible_when_logged_in(self):
        dashboard_url = reverse('tasks:dashboard')
        self.client.login(username='viewtester', password='password123')
        response = self.client.get(dashboard_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tasks/dashboard.html')
    def test_login_page_renders(self):
        login_url = reverse('login')
        response = self.client.get(login_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/login.html')
    def test_register_page_renders(self):
        register_url = reverse('register')
        response = self.client.get(register_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/register.html')

# --- Group View Tests ---
class GroupViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username='groupowner', password='password123')
        cls.member = User.objects.create_user(username='groupmember', password='password123')
        cls.non_member = User.objects.create_user(username='nonmember', password='password123')
        cls.group = Group.objects.create(name='Group View Test Group', owner=cls.owner)
        cls.group.members.add(cls.owner, cls.member)
    def setUp(self):
        self.client = Client()

    def test_group_create_view_requires_login(self):
        group_create_url = reverse('tasks:group_create')
        login_url = reverse('login')
        response = self.client.get(group_create_url)
        self.assertRedirects(response, f'{login_url}?next={group_create_url}')
    def test_group_create_view_get_renders(self):
        group_create_url = reverse('tasks:group_create')
        self.client.login(username='groupowner', password='password123')
        response = self.client.get(group_create_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tasks/group_form.html')
        self.assertContains(response, 'Create New Group')
    def test_group_create_view_post_creates_group(self):
        group_create_url = reverse('tasks:group_create')
        dashboard_url = reverse('tasks:dashboard')
        self.client.login(username='groupowner', password='password123')
        group_data = {'name': 'New Group via Test', 'description': 'Testing creation'}
        response = self.client.post(group_create_url, group_data)
        self.assertRedirects(response, dashboard_url)
        new_group = Group.objects.get(name='New Group via Test')
        self.assertEqual(new_group.owner, self.owner)
        self.assertIn(self.owner, new_group.members.all())
    def test_group_detail_view_requires_login(self):
        group_detail_url = reverse('tasks:group_detail', kwargs={'pk': self.group.pk})
        login_url = reverse('login')
        response = self.client.get(group_detail_url)
        self.assertRedirects(response, f'{login_url}?next={group_detail_url}')
    def test_group_detail_view_member_access(self):
        group_detail_url = reverse('tasks:group_detail', kwargs={'pk': self.group.pk})
        self.client.login(username='groupmember', password='password123')
        response = self.client.get(group_detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tasks/group_detail.html')
        self.assertContains(response, self.group.name)
    def test_group_detail_view_non_member_access_denied(self):
        group_detail_url = reverse('tasks:group_detail', kwargs={'pk': self.group.pk})
        self.client.login(username='nonmember', password='password123')
        response = self.client.get(group_detail_url)
        self.assertEqual(response.status_code, 403)
    def test_group_update_view_requires_login(self):
        group_update_url = reverse('tasks:group_update', kwargs={'pk': self.group.pk})
        login_url = reverse('login')
        response = self.client.get(group_update_url)
        self.assertRedirects(response, f'{login_url}?next={group_update_url}')
    def test_group_update_view_member_access_denied(self):
        group_update_url = reverse('tasks:group_update', kwargs={'pk': self.group.pk})
        self.client.login(username='groupmember', password='password123')
        response = self.client.get(group_update_url)
        self.assertEqual(response.status_code, 403)
    def test_group_update_view_owner_get_renders(self):
        group_update_url = reverse('tasks:group_update', kwargs={'pk': self.group.pk})
        self.client.login(username='groupowner', password='password123')
        response = self.client.get(group_update_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tasks/group_form.html')
        self.assertContains(response, 'Edit Group')
    def test_group_update_view_owner_post_updates(self):
        group_update_url = reverse('tasks:group_update', kwargs={'pk': self.group.pk})
        group_detail_url = reverse('tasks:group_detail', kwargs={'pk': self.group.pk})
        self.client.login(username='groupowner', password='password123')
        updated_data = {'name': 'Updated Group Name', 'description': 'Updated Desc'}
        response = self.client.post(group_update_url, updated_data)
        self.assertRedirects(response, group_detail_url)
        self.group.refresh_from_db()
        self.assertEqual(self.group.name, 'Updated Group Name')
        self.assertEqual(self.group.description, 'Updated Desc')
    def test_group_delete_view_requires_login(self):
        group_delete_url = reverse('tasks:group_delete', kwargs={'pk': self.group.pk})
        login_url = reverse('login')
        response = self.client.get(group_delete_url)
        self.assertRedirects(response, f'{login_url}?next={group_delete_url}')
    def test_group_delete_view_member_access_denied(self):
        group_delete_url = reverse('tasks:group_delete', kwargs={'pk': self.group.pk})
        self.client.login(username='groupmember', password='password123')
        response = self.client.get(group_delete_url)
        self.assertEqual(response.status_code, 403)
        response = self.client.post(group_delete_url)
        self.assertEqual(response.status_code, 403)
    def test_group_delete_view_owner_get_renders(self):
        group_delete_url = reverse('tasks:group_delete', kwargs={'pk': self.group.pk})
        self.client.login(username='groupowner', password='password123')
        response = self.client.get(group_delete_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tasks/group_confirm_delete.html')
    def test_group_delete_view_owner_post_deletes(self):
        group_delete_url = reverse('tasks:group_delete', kwargs={'pk': self.group.pk})
        dashboard_url = reverse('tasks:dashboard')
        self.client.login(username='groupowner', password='password123')
        response = self.client.post(group_delete_url)
        self.assertRedirects(response, dashboard_url)
        with self.assertRaises(Group.DoesNotExist):
            Group.objects.get(pk=self.group.pk)


# --- Task View Tests ---
class TaskViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username='taskviewowner', password='password123')
        cls.member = User.objects.create_user(username='taskviewmember', password='password123')
        cls.non_member = User.objects.create_user(username='taskviewnonmember', password='password123')
        cls.group = Group.objects.create(name='Task View Test Group', owner=cls.owner)
        cls.group.members.add(cls.owner, cls.member)
        cls.task = Task.objects.create(group=cls.group, title='Task View Test Task', creator=cls.owner)
    def setUp(self):
        self.client = Client()

    def test_task_create_view_requires_login(self):
        task_create_url = reverse('tasks:task_create', kwargs={'group_pk': self.group.pk})
        login_url = reverse('login')
        response = self.client.get(task_create_url)
        self.assertRedirects(response, f'{login_url}?next={task_create_url}')
    def test_task_create_view_non_member_denied(self):
        task_create_url = reverse('tasks:task_create', kwargs={'group_pk': self.group.pk})
        self.client.login(username='taskviewnonmember', password='password123')
        response = self.client.get(task_create_url)
        self.assertEqual(response.status_code, 403)
    def test_task_create_view_member_get_renders(self):
        task_create_url = reverse('tasks:task_create', kwargs={'group_pk': self.group.pk})
        self.client.login(username='taskviewmember', password='password123')
        response = self.client.get(task_create_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tasks/task_form.html')
        self.assertContains(response, 'Add New Task')
    def test_task_create_view_member_post_creates_task(self):
        task_create_url = reverse('tasks:task_create', kwargs={'group_pk': self.group.pk})
        group_detail_url = reverse('tasks:group_detail', kwargs={'pk': self.group.pk})
        self.client.login(username='taskviewmember', password='password123')
        task_data = {'title': 'New Task By Member', 'description': 'Testing task creation'}
        response = self.client.post(task_create_url, task_data)
        self.assertRedirects(response, group_detail_url)
        new_task = Task.objects.get(title='New Task By Member')
        self.assertEqual(new_task.group, self.group)
        self.assertEqual(new_task.creator, self.member)
    def test_task_update_view_requires_login(self):
        task_update_url = reverse('tasks:task_update', kwargs={'pk': self.task.pk})
        login_url = reverse('login')
        response = self.client.get(task_update_url)
        self.assertRedirects(response, f'{login_url}?next={task_update_url}')
    def test_task_update_view_non_member_denied(self):
        task_update_url = reverse('tasks:task_update', kwargs={'pk': self.task.pk})
        self.client.login(username='taskviewnonmember', password='password123')
        response = self.client.get(task_update_url)
        self.assertEqual(response.status_code, 403)
    def test_task_update_view_member_get_renders(self):
        task_update_url = reverse('tasks:task_update', kwargs={'pk': self.task.pk})
        self.client.login(username='taskviewmember', password='password123')
        response = self.client.get(task_update_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tasks/task_form.html')
        self.assertContains(response, 'Edit Task')
    
    def test_task_update_view_member_post_updates(self):
        task_update_url = reverse('tasks:task_update', kwargs={'pk': self.task.pk})
        group_detail_url = reverse('tasks:group_detail', kwargs={'pk': self.group.pk})
        self.client.login(username='taskviewmember', password='password123')
        updated_data = {
            'title': 'Updated Task Title',
            'description': self.task.description or '' 
        }
        response = self.client.post(task_update_url, updated_data)
        self.assertRedirects(response, group_detail_url)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, 'Updated Task Title')
        
    def test_task_delete_view_requires_login(self):
        task_delete_url = reverse('tasks:task_delete', kwargs={'pk': self.task.pk})
        login_url = reverse('login')
        response = self.client.get(task_delete_url)
        self.assertRedirects(response, f'{login_url}?next={task_delete_url}')
    def test_task_delete_view_non_member_denied(self):
        task_delete_url = reverse('tasks:task_delete', kwargs={'pk': self.task.pk})
        self.client.login(username='taskviewnonmember', password='password123')
        response = self.client.get(task_delete_url)
        self.assertEqual(response.status_code, 403)
    def test_task_delete_view_member_non_creator_denied(self):
        task_delete_url = reverse('tasks:task_delete', kwargs={'pk': self.task.pk})
        self.client.login(username='taskviewmember', password='password123')
        response_get = self.client.get(task_delete_url)
        self.assertEqual(response_get.status_code, 403)
        response_post = self.client.post(task_delete_url)
        self.assertEqual(response_post.status_code, 403)
    def test_task_delete_view_creator_get_renders(self):
        task_delete_url = reverse('tasks:task_delete', kwargs={'pk': self.task.pk})
        self.client.login(username='taskviewowner', password='password123')
        response = self.client.get(task_delete_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tasks/task_confirm_delete.html')
    def test_task_delete_view_creator_post_deletes(self):
        task_delete_url = reverse('tasks:task_delete', kwargs={'pk': self.task.pk})
        group_detail_url = reverse('tasks:group_detail', kwargs={'pk': self.group.pk})
        self.client.login(username='taskviewowner', password='password123')
        response = self.client.post(task_delete_url)
        self.assertRedirects(response, group_detail_url)
        with self.assertRaises(Task.DoesNotExist):
            Task.objects.get(pk=self.task.pk)
    def test_toggle_task_requires_login(self):
        task_toggle_url = reverse('tasks:toggle_task_complete', kwargs={'pk': self.task.pk})
        login_url = reverse('login')
        response = self.client.post(task_toggle_url)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, f'{login_url}?next={task_toggle_url}')
    def test_toggle_task_non_member_denied(self):
        task_toggle_url = reverse('tasks:toggle_task_complete', kwargs={'pk': self.task.pk})
        self.client.login(username='taskviewnonmember', password='password123')
        response = self.client.post(task_toggle_url)
        self.assertEqual(response.status_code, 403)
    def test_toggle_task_member_toggles_status(self):
        task_toggle_url = reverse('tasks:toggle_task_complete', kwargs={'pk': self.task.pk})
        group_detail_url = reverse('tasks:group_detail', kwargs={'pk': self.group.pk})
        self.client.login(username='taskviewmember', password='password123')
        self.assertEqual(self.task.status, Task.STATUS_OPEN)
        response1 = self.client.post(task_toggle_url)
        self.assertRedirects(response1, group_detail_url)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.STATUS_COMPLETE)
        response2 = self.client.post(task_toggle_url)
        self.assertRedirects(response2, group_detail_url)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.STATUS_OPEN)
    def test_toggle_task_member_ajax_toggles_status(self):
        task_toggle_url = reverse('tasks:toggle_task_complete', kwargs={'pk': self.task.pk})
        self.client.login(username='taskviewmember', password='password123')
        self.assertEqual(self.task.status, Task.STATUS_OPEN)
        ajax_headers = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}
        response1 = self.client.post(task_toggle_url, **ajax_headers)
        self.assertEqual(response1.status_code, 200)
        json_data1 = json.loads(response1.content)
        self.assertTrue(json_data1['success'])
        self.assertTrue(json_data1['is_complete'])
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.STATUS_COMPLETE)
        response2 = self.client.post(task_toggle_url, **ajax_headers)
        self.assertEqual(response2.status_code, 200)
        json_data2 = json.loads(response2.content)
        self.assertTrue(json_data2['success'])
        self.assertFalse(json_data2['is_complete'])
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.STATUS_OPEN)
    def test_toggle_task_non_member_ajax_denied(self):
        task_toggle_url = reverse('tasks:toggle_task_complete', kwargs={'pk': self.task.pk})
        self.client.login(username='taskviewnonmember', password='password123')
        ajax_headers = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}
        response = self.client.post(task_toggle_url, **ajax_headers)
        self.assertEqual(response.status_code, 403)
        json_data = json.loads(response.content)
        self.assertFalse(json_data['success'])
        self.assertEqual(json_data['error'], 'Permission denied')


# --- Member Management View Tests ---
class MemberManagementViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username='memberowner', password='password123')
        cls.member1 = User.objects.create_user(username='member1', password='password123')
        cls.member2 = User.objects.create_user(username='member2', password='password123')
        cls.non_member = User.objects.create_user(username='membernonmember', password='password123')
        cls.group = Group.objects.create(name='Member Test Group', owner=cls.owner)
        cls.group.members.add(cls.owner, cls.member1)
    def setUp(self):
        self.client = Client()
        self.client.login(username='memberowner', password='password123') 

    def test_add_member_requires_login(self):
        self.client.logout()
        add_member_url = reverse('tasks:add_member', kwargs={'group_pk': self.group.pk})
        login_url = reverse('login')
        response = self.client.get(add_member_url)
        self.assertRedirects(response, f'{login_url}?next={add_member_url}')
    
    def test_add_member_non_owner_denied(self):
        add_member_url = reverse('tasks:add_member', kwargs={'group_pk': self.group.pk})
        group_detail_url = reverse('tasks:group_detail', kwargs={'pk': self.group.pk})
        self.client.login(username='member1', password='password123')
        response = self.client.get(add_member_url, follow=True)
        self.assertRedirects(response, group_detail_url)
        messages = list(response.context['messages'])
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "Only the group owner can add members.")
        
    def test_add_member_owner_get_renders(self):
        add_member_url = reverse('tasks:add_member', kwargs={'group_pk': self.group.pk})
        response = self.client.get(add_member_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tasks/add_member.html')
        self.assertContains(response, 'Add New Member')
    
    def test_add_member_owner_post_adds_member(self):
        add_member_url = reverse('tasks:add_member', kwargs={'group_pk': self.group.pk})
        add_data = {'username': 'member2'}
        response = self.client.post(add_member_url, add_data, follow=True)
        self.assertRedirects(response, add_member_url)
        self.group.refresh_from_db()
        self.assertIn(self.member2, self.group.members.all())
        self.assertContains(response, "User 'member2' added successfully.")
        
    def test_add_member_owner_post_already_member(self):
        add_member_url = reverse('tasks:add_member', kwargs={'group_pk': self.group.pk})
        add_data = {'username': 'member1'}
        response = self.client.post(add_member_url, add_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already a member")
        self.group.refresh_from_db()
        self.assertEqual(self.group.members.count(), 2)
    def test_add_member_owner_post_nonexistent_user(self):
        add_member_url = reverse('tasks:add_member', kwargs={'group_pk': self.group.pk})
        add_data = {'username': 'nouser'}
        response = self.client.post(add_member_url, add_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "does not exist")

    def test_remove_member_requires_login(self):
        self.client.logout()
        remove_url = reverse('tasks:remove_member', kwargs={'group_pk': self.group.pk, 'user_pk': self.member1.pk})
        login_url = reverse('login')
        response = self.client.post(remove_url)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, f'{login_url}?next={remove_url}')
    
    def test_remove_member_non_owner_denied(self):
        remove_url = reverse('tasks:remove_member', kwargs={'group_pk': self.group.pk, 'user_pk': self.owner.pk})
        group_detail_url = reverse('tasks:group_detail', kwargs={'pk': self.group.pk})
        self.client.login(username='member1', password='password123')
        response = self.client.post(remove_url, follow=True)
        self.assertRedirects(response, group_detail_url)
        messages = list(response.context['messages'])
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "Only the group owner can remove members.")
        
    def test_remove_member_owner_cannot_remove_self(self):
        remove_url = reverse('tasks:remove_member', kwargs={'group_pk': self.group.pk, 'user_pk': self.owner.pk})
        add_member_url = reverse('tasks:add_member', kwargs={'group_pk': self.group.pk})
        response = self.client.post(remove_url, follow=True)
        self.assertRedirects(response, add_member_url)
        self.assertContains(response, "owner cannot be removed")
        self.assertIn(self.owner, self.group.members.all())
        
    def test_remove_member_owner_removes_member(self):
        remove_url = reverse('tasks:remove_member', kwargs={'group_pk': self.group.pk, 'user_pk': self.member1.pk})
        add_member_url = reverse('tasks:add_member', kwargs={'group_pk': self.group.pk})
        self.assertIn(self.member1, self.group.members.all())
        response = self.client.post(remove_url, follow=True)
        self.assertRedirects(response, add_member_url)
        self.group.refresh_from_db()
        self.assertNotIn(self.member1, self.group.members.all())
        self.assertContains(response, f"User '{self.member1.username}' removed successfully.")

    def test_leave_group_requires_login(self):
        self.client.logout()
        leave_url = reverse('tasks:leave_group', kwargs={'group_pk': self.group.pk})
        login_url = reverse('login')
        response = self.client.post(leave_url)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, f'{login_url}?next={leave_url}')
    
    def test_leave_group_non_member_redirects(self):
        leave_url = reverse('tasks:leave_group', kwargs={'group_pk': self.group.pk})
        dashboard_url = reverse('tasks:dashboard')
        self.client.login(username='nonmember', password='password123')
        response = self.client.post(leave_url, follow=True)
        self.assertRedirects(response, dashboard_url)
        messages = list(response.context['messages'])
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "You are not a member of this group.")
        
    def test_leave_group_owner_cannot_leave(self):
        leave_url = reverse('tasks:leave_group', kwargs={'group_pk': self.group.pk})
        group_detail_url = reverse('tasks:group_detail', kwargs={'pk': self.group.pk})
        response = self.client.post(leave_url, follow=True)
        self.assertRedirects(response, group_detail_url)
        self.assertContains(response, "owner cannot leave the group")
        self.assertIn(self.owner, self.group.members.all())
        
    def test_leave_group_member_leaves(self):
        leave_url = reverse('tasks:leave_group', kwargs={'group_pk': self.group.pk})
        dashboard_url = reverse('tasks:dashboard')
        self.client.login(username='member1', password='password123')
        self.assertIn(self.member1, self.group.members.all())
        response = self.client.post(leave_url, follow=True)
        self.assertRedirects(response, dashboard_url)
        self.group.refresh_from_db()
        self.assertNotIn(self.member1, self.group.members.all())
        messages = list(response.context.get('messages', []))
        self.assertTrue(any(f"You have left the group '{self.group.name}'." in str(m) for m in messages))


# --- Form Tests ---
class GroupFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        pass

    def test_valid_group_form(self):
        data = {'name': 'Valid Group Name'}
        form = GroupForm(data=data)
        self.assertTrue(form.is_valid())
    def test_valid_group_form_with_description(self):
        data = {'name': 'Valid Group Name 2', 'description': 'Optional desc.'}
        form = GroupForm(data=data)
        self.assertTrue(form.is_valid())
    def test_invalid_group_form_missing_name(self):
        data = {'description': 'Missing name'}
        form = GroupForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)
        self.assertIn('required', form.errors['name'][0])

class TaskFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username='formowner', password='password123')
        cls.member1 = User.objects.create_user(username='formmember1', password='password123')
        cls.member2 = User.objects.create_user(username='formmember2', password='password123')
        cls.outsider = User.objects.create_user(username='formoutsider', password='password123')
        cls.group = Group.objects.create(name='Form Test Group', owner=cls.owner)
        cls.group.members.add(cls.owner, cls.member1, cls.member2)
    def test_valid_task_form_minimal(self):
        data = {'title': 'Minimal Valid Task'}
        form = TaskForm(data=data, group=self.group)
        self.assertTrue(form.is_valid())
    def test_valid_task_form_all_fields(self):
        data = {
            'title': 'Full Valid Task','description': 'With all details.',
            'assigned_to': self.member1.pk,
            'due_date': timezone.now().date() + datetime.timedelta(days=1)
        }
        form = TaskForm(data=data, group=self.group)
        self.assertTrue(form.is_valid())
    def test_invalid_task_form_missing_title(self):
        data = {'description': 'No title'}
        form = TaskForm(data=data, group=self.group)
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)
        self.assertIn('required', form.errors['title'][0])
    def test_invalid_task_form_assignee_not_member(self):
        data = {'title': 'Assign to Outsider', 'assigned_to': self.outsider.pk }
        form = TaskForm(data=data, group=self.group)
        self.assertFalse(form.is_valid())
        self.assertIn('assigned_to', form.errors)
        self.assertTrue(any('Select a valid choice' in error for error in form.errors['assigned_to']))
    def test_task_form_assigned_to_queryset_filtered(self):
        form = TaskForm(group=self.group)
        expected_members = list(self.group.members.all().order_by('username'))
        actual_members = list(form.fields['assigned_to'].queryset)
        self.assertListEqual(actual_members, expected_members)
        self.assertNotIn(self.outsider, actual_members)

class AddMemberFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.existing_user = User.objects.create_user(username='exists', password='password123')
    def test_valid_add_member_form(self):
        data = {'username': 'exists'}
        form = AddMemberForm(data=data)
        self.assertTrue(form.is_valid())
    def test_invalid_add_member_form_nonexistent(self):
        data = {'username': 'doesnotexist'}
        form = AddMemberForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)
        self.assertIn('does not exist', form.errors['username'][0])
    def test_invalid_add_member_form_empty(self):
        data = {'username': ''}
        form = AddMemberForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)
        self.assertIn('required', form.errors['username'][0])

class PledgeFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        pass
        
    def test_valid_pledge_form(self):
        data = {'amount': 100}
        form = PledgeForm(data=data)
        self.assertTrue(form.is_valid())
    def test_invalid_pledge_form_zero_amount(self):
        data = {'amount': 0}
        form = PledgeForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('amount', form.errors)
        self.assertIn('greater than zero', form.errors['amount'][0])
    def test_invalid_pledge_form_negative_amount(self):
        data = {'amount': -50}
        form = PledgeForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('amount', form.errors)
        self.assertIn('greater than zero', form.errors['amount'][0])
    def test_invalid_pledge_form_empty(self):
        data = {}
        form = PledgeForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('amount', form.errors)

class TaskSubmissionFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        pass
        
    def test_valid_submission_form_text_only(self):
        data = {'proof_text': 'Here is my proof.'}
        form = TaskSubmissionForm(data=data)
        self.assertTrue(form.is_valid())
    def test_valid_submission_form_link_only(self):
        data = {'proof_link': 'https://example.com'}
        form = TaskSubmissionForm(data=data)
        self.assertTrue(form.is_valid())
    def test_valid_submission_form_both(self):
        data = {'proof_text': 'See link.', 'proof_link': 'https://example.com'}
        form = TaskSubmissionForm(data=data)
        self.assertTrue(form.is_valid())
    def test_invalid_submission_form_empty(self):
        data = {'proof_text': '', 'proof_link': ''}
        form = TaskSubmissionForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)
        self.assertIn('must provide either text proof or a link', form.errors['__all__'][0])
    def test_invalid_submission_form_bad_link(self):
        data = {'proof_link': 'not a valid link'}
        form = TaskSubmissionForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('proof_link', form.errors)
        self.assertIn('Enter a valid URL', form.errors['proof_link'][0])

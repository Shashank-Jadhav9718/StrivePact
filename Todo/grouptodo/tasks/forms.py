from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
# Import all models used in forms
from .models import Group, Task, WeeklyPledge, TaskSubmission

# --- Registration Form ---
class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'})
    )
    class Meta:
        model = User
        fields = ("username", "email")
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}),
        }
    def __init__(self, *args, **kwargs):
        super(UserRegistrationForm, self).__init__(*args, **kwargs)
        self.fields['password1'].widget = forms.PasswordInput(
            attrs={'class': 'form-control', 'placeholder': 'Password'}
        )
        self.fields['password1'].label = "Password"
        self.fields['password2'].widget = forms.PasswordInput(
            attrs={'class': 'form-control', 'placeholder': 'Confirm Password'}
        )
        self.fields['password2'].label = "Confirm Password"

# --- Login Form ---
class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(
        attrs={'class': 'form-control', 'placeholder': 'Username'}
    ))
    password = forms.CharField(widget=forms.PasswordInput(
        attrs={'class': 'form-control', 'placeholder': 'Password'}
    ))

# --- Group Form ---
class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Group Name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional: Describe the group...'}),
        }

# --- Task Form ---
class TaskForm(forms.ModelForm):
    assigned_to = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    due_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    requires_proof = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Require proof of work for this task?"
    )

    class Meta:
        model = Task
        fields = ['title', 'description', 'assigned_to', 'due_date', 'requires_proof']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Task Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Optional: Task details...'}),
        }

    def __init__(self, *args, **kwargs):
        group = kwargs.pop('group', None)
        super(TaskForm, self).__init__(*args, **kwargs)
        
        if group:
            self.fields['assigned_to'].queryset = group.members.all().order_by('username')
        elif self.instance and self.instance.pk and self.instance.group:
            self.fields['assigned_to'].queryset = self.instance.group.members.all().order_by('username')

# --- Add Member Form ---
class AddMemberForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter username to add'})
    )
    def clean_username(self):
        username = self.cleaned_data.get('username')
        try:
            User.objects.get(username=username)
        except User.DoesNotExist:
            raise forms.ValidationError("User with this username does not exist.")
        return username

# --- Pledge Form ---
class PledgeForm(forms.ModelForm):
    class Meta:
        model = WeeklyPledge
        fields = ['amount']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 100'})
        }
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount <= 0:
            raise forms.ValidationError("Pledge amount must be greater than zero.")
        return amount

# --- Task Submission Form ---
class TaskSubmissionForm(forms.ModelForm):
    class Meta:
        model = TaskSubmission
        fields = ['proof_text', 'proof_link']
        widgets = {
            'proof_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Add your proof or comments here...'}),
            'proof_link': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://github.com/your-repo...'}),
        }
        labels = {
            'proof_text': 'Proof (Text)',
            'proof_link': 'Proof (Link)',
        }
    
    def clean(self):
        cleaned_data = super().clean()
        proof_text = cleaned_data.get('proof_text')
        proof_link = cleaned_data.get('proof_link')
        
        if not proof_text and not proof_link:
            raise forms.ValidationError("You must provide either text proof or a link.")
        return cleaned_data

# --- NEW: Submission Review Form ---
class SubmissionReviewForm(forms.ModelForm):
    """Form for a peer to leave a review comment."""
    class Meta:
        model = TaskSubmission
        fields = ['review_comment'] # Only the comment is needed from the form
        widgets = {
            'review_comment': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 4, 
                'placeholder': 'Provide feedback (optional for approval, required for revision)...'
            })
        }
        labels = {
            'review_comment': 'Feedback Comment'
        }


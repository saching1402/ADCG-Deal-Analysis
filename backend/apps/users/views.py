from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import Role, User


class LoginSerializer(TokenObtainPairSerializer):
    """Accepts an email OR a username in the 'email' field (case-insensitive)."""
    def validate(self, attrs):
        who = (attrs.get(self.username_field) or '').strip()
        u = User.objects.filter(email__iexact=who).first() if '@' in who else User.objects.filter(username__iexact=who).first()
        if u:
            attrs[self.username_field] = u.email
        data = super().validate(attrs)
        User.objects.filter(pk=self.user.pk).update(last_login=timezone.now())
        return data


class ThrottledTokenObtainPairView(TokenObtainPairView):
    """Email-or-username + password login; rate-limited per IP."""
    throttle_scope = 'login'
    serializer_class = LoginSerializer


def is_admin(u) -> bool:
    return bool(u and (u.is_superuser or u.role == Role.ADMIN))


def user_json(u: User) -> dict:
    return {'id': str(u.id), 'email': u.email, 'username': u.username or '', 'full_name': u.full_name, 'role': u.role,
            'is_active': u.is_active, 'is_staff': u.is_staff, 'is_admin': is_admin(u), 'last_login': u.last_login,
            'date_joined': u.date_joined, 'starter_password': u.password_changed_at is None}


def _profile(u: User, data: dict, *, admin: bool) -> dict:
    """Apply editable fields; returns {field: error} on problems."""
    errs = {}
    if 'full_name' in data:
        u.full_name = str(data['full_name'] or '').strip()[:255]
    if 'username' in data:
        un = str(data['username'] or '').strip().lower() or None
        if un and (not un.replace('.', '').replace('_', '').replace('-', '').isalnum() or len(un) > 40):
            errs['username'] = 'Use letters, numbers, dots, dashes or underscores.'
        elif un and User.objects.filter(username__iexact=un).exclude(pk=u.pk).exists():
            errs['username'] = 'That username is taken.'
        else:
            u.username = un
    if 'email' in data:
        em = str(data['email'] or '').strip().lower()
        if '@' not in em:
            errs['email'] = 'Enter a valid email address.'
        elif User.objects.filter(email__iexact=em).exclude(pk=u.pk).exists():
            errs['email'] = 'That email is already used by another account.'
        else:
            u.email = em
    if admin and 'role' in data and data['role'] in Role.values:
        u.role = data['role']
    if admin and 'is_active' in data:
        u.is_active = bool(data['is_active'])
    return errs


class MeView(APIView):
    def get(self, request):
        return Response(user_json(request.user))

    def patch(self, request):
        u = request.user
        errs = _profile(u, {k: v for k, v in request.data.items() if k in ('full_name', 'username', 'email')}, admin=False)
        if errs:
            return Response({'detail': ' '.join(errs.values()), 'errors': errs}, status=400)
        u.save()
        return Response(user_json(u))


class PasswordView(APIView):
    """POST {current_password, new_password} — change your own password."""
    def post(self, request):
        u = request.user
        if not u.check_password(request.data.get('current_password') or ''):
            return Response({'detail': 'Your current password is not correct.'}, status=400)
        new = request.data.get('new_password') or ''
        if new == request.data.get('current_password'):
            return Response({'detail': 'Choose a password different from the current one.'}, status=400)
        try:
            validate_password(new, u)
        except ValidationError as e:
            return Response({'detail': ' '.join(e.messages)}, status=400)
        u.set_password(new)
        u.password_changed_at = timezone.now()
        u.save()
        return Response({'ok': True})


class UserList(APIView):
    """GET everyone (any signed-in user — names for the activity log); POST creates a user (admins)."""
    def get(self, request):
        return Response({'users': [user_json(u) for u in User.objects.order_by('full_name', 'email')],
                         'can_manage': is_admin(request.user)})

    def post(self, request):
        if not is_admin(request.user):
            return Response({'detail': 'Only admins can add users.'}, status=403)
        d = request.data
        un = str(d.get('username') or '').strip().lower()
        em = str(d.get('email') or '').strip().lower() or (f'{un}@deal-analysis.local' if un else '')
        if not un and not em:
            return Response({'detail': 'Give a username or an email.'}, status=400)
        u = User(email=em, role=d.get('role') if d.get('role') in Role.values else Role.ANALYST)
        errs = _profile(u, {'username': un or None, 'email': em, 'full_name': d.get('full_name', '')}, admin=True)
        if errs:
            return Response({'detail': ' '.join(errs.values()), 'errors': errs}, status=400)
        pw = d.get('password') or ''
        try:
            validate_password(pw, u)
        except ValidationError as e:
            return Response({'detail': ' '.join(e.messages)}, status=400)
        u.set_password(pw)
        u.save()
        return Response(user_json(u), status=201)


class UserDetail(APIView):
    """PATCH {full_name, username, email, role, is_active} — admins."""
    def patch(self, request, pk):
        if not is_admin(request.user):
            return Response({'detail': 'Only admins can change other users.'}, status=403)
        u = User.objects.filter(pk=pk).first()
        if not u:
            return Response({'detail': 'User not found.'}, status=404)
        if u.pk == request.user.pk and (request.data.get('is_active') is False or request.data.get('role') not in (None, Role.ADMIN)):
            return Response({'detail': 'You cannot deactivate yourself or remove your own admin role.'}, status=400)
        errs = _profile(u, request.data, admin=True)
        if errs:
            return Response({'detail': ' '.join(errs.values()), 'errors': errs}, status=400)
        u.save()
        return Response(user_json(u))


class UserResetPassword(APIView):
    """POST {password} — admins set a new starter password for someone (they should change it after signing in)."""
    def post(self, request, pk):
        if not is_admin(request.user):
            return Response({'detail': 'Only admins can reset passwords.'}, status=403)
        u = User.objects.filter(pk=pk).first()
        if not u:
            return Response({'detail': 'User not found.'}, status=404)
        pw = request.data.get('password') or ''
        try:
            validate_password(pw, u)
        except ValidationError as e:
            return Response({'detail': ' '.join(e.messages)}, status=400)
        u.set_password(pw)
        u.password_changed_at = None
        u.save()
        return Response(user_json(u))

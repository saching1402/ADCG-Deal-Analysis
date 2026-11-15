"""
Custom User model.
Username login (email optional), UUID primary key, roles ADMIN > ANALYST > VIEWER, Argon2 hashing.
"""
import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Role(models.TextChoices):
    ADMIN = 'admin', _('Admin')
    ANALYST = 'analyst', _('Analyst')
    VIEWER = 'viewer', _('Viewer')


class UserManager(BaseUserManager):
    def _create_user(self, username: str | None, password: str | None, email: str | None = None, **extra):
        email = self.normalize_email(email) if email else None
        username = (username or (email.split('@')[0] if email else '')).strip().lower()
        if not username:
            raise ValueError('A username is required.')
        user = self.model(username=username, email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, username: str | None = None, password: str | None = None, **extra):
        extra.setdefault('is_staff', False)
        extra.setdefault('is_superuser', False)
        return self._create_user(username, password, **extra)

    def create_superuser(self, username: str | None = None, password: str | None = None, **extra):
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        extra.setdefault('role', Role.ADMIN)
        return self._create_user(username, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=40, unique=True)                        # what people sign in with
    email = models.EmailField(_('email address'), unique=True, null=True, blank=True)  # optional; also works to sign in
    full_name = models.CharField(max_length=255, blank=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.VIEWER)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    password_changed_at = models.DateTimeField(null=True, blank=True)   # null = still on the starter password

    objects = UserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        db_table = 'users'
        ordering = ['username']

    def __str__(self) -> str:
        return self.username

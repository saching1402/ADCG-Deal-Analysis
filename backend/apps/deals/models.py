"""Deal pipeline: deals, their uploaded materials, and analysis runs."""
import os
import uuid

from django.conf import settings
from django.db import models


class Track(models.TextChoices):
    AUTO = 'auto', 'Auto-detect'
    BUYOUT = 'buyout', 'Buyout / co-invest / CV'
    VG = 'vg', 'Venture / Growth'


class Stage(models.TextChoices):
    NEW = 'new', 'New'
    ANALYZED = 'analyzed', 'Analyzed'
    INTERNAL = 'internal', 'Internal Team Approval'
    PRE_IC = 'pre_ic', 'Pre-IC'
    FINAL_IC = 'final_ic', 'Final IC'
    APPROVED = 'approved', 'Approved'
    PASSED = 'passed', 'Passed / Declined'
    ON_HOLD = 'on_hold', 'On hold'


class Status(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    QUEUED = 'queued', 'Queued'
    RUNNING = 'running', 'Running'
    DONE = 'done', 'Done'
    ERROR = 'error', 'Error'


class Deal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    website = models.CharField(max_length=500, blank=True)
    track = models.CharField(max_length=10, choices=Track.choices, default=Track.AUTO)  # requested
    track_resolved = models.CharField(max_length=10, blank=True)  # buyout | vg once analysed
    sponsor = models.CharField(max_length=500, blank=True)  # sponsor / lead investors as entered or found
    sector = models.CharField(max_length=255, blank=True)
    sub_sector = models.CharField(max_length=500, blank=True)
    notes = models.TextField(blank=True)  # deal terms / context typed by the deal lead
    stage = models.CharField(max_length=12, choices=Stage.choices, default=Stage.NEW)

    # headline outputs (also editable for seeded ledger rows)
    ev = models.CharField(max_length=255, blank=True)
    multiple = models.CharField(max_length=255, blank=True)
    leverage = models.CharField(max_length=255, blank=True)
    one_liner = models.TextField(blank=True)
    adcg_score = models.FloatField(null=True, blank=True)
    risk_score = models.IntegerField(null=True, blank=True)
    band = models.CharField(max_length=20, blank=True)
    recommendation = models.TextField(blank=True)
    facts = models.JSONField(default=list, blank=True)       # [{k, v}]
    summary = models.JSONField(default=dict, blank=True)     # engine summary (sections, vjr, marquee…)
    scorecard = models.JSONField(default=dict, blank=True)   # full deal JSON (criteria + rationales)
    research = models.TextField(blank=True)                  # research dossier (markdown)
    memo_html = models.TextField(blank=True)                 # assembled IC memo
    sources = models.JSONField(default=list, blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    legacy = models.BooleanField(default=False)  # seeded from the ledger (scores only, no memo here)
    analyzed_at = models.DateTimeField(null=True, blank=True)
    total_cost = models.FloatField(default=0.0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.name


def upload_to(instance, filename):
    return f'deals/{instance.deal_id}/{uuid.uuid4().hex[:8]}-{os.path.basename(filename)[:180]}'


class DealFile(models.Model):
    STATUS = [('uploaded', 'Uploaded'), ('digesting', 'Digesting'), ('digested', 'Digested'), ('error', 'Error')]
    deal = models.ForeignKey(Deal, related_name='files', on_delete=models.CASCADE)
    file = models.FileField(upload_to=upload_to, max_length=500)
    name = models.CharField(max_length=255)
    size = models.BigIntegerField(default=0)
    content_type = models.CharField(max_length=150, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default='uploaded')
    method = models.CharField(max_length=20, blank=True)  # native-pdf | text | image
    pages = models.IntegerField(null=True, blank=True)
    chars = models.IntegerField(null=True, blank=True)
    digest = models.TextField(blank=True)  # structured fact sheet Claude wrote for this file
    error = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']


class AnalysisJob(models.Model):
    STAGES = ['digest', 'research', 'score', 'memo']
    deal = models.ForeignKey(Deal, related_name='jobs', on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.QUEUED)
    stage = models.CharField(max_length=20, blank=True)
    stage_detail = models.CharField(max_length=500, blank=True)
    model = models.CharField(max_length=60, blank=True)
    digest_model = models.CharField(max_length=60, blank=True)
    instructions = models.TextField(blank=True)  # extra steer for this run (e.g. rationale for key risks)
    input_tokens = models.BigIntegerField(default=0)
    output_tokens = models.BigIntegerField(default=0)
    searches = models.IntegerField(default=0)
    cost = models.FloatField(default=0.0)
    log = models.JSONField(default=list, blank=True)  # [{t, msg}]
    error = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

"""Deal pipeline: deals, their uploaded materials, and analysis runs."""
import os
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Track(models.TextChoices):
    AUTO = 'auto', 'Auto-detect'
    BUYOUT = 'buyout', 'Buyout / co-invest'
    CV = 'cv', 'CV / GP-led secondary'
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
    BLOCKED = 'blocked', 'Files need attention'


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
    risk_review = models.TextField(blank=True)               # independent risk review (markdown)
    risk_items = models.JSONField(default=dict, blank=True)  # {risks:[…], track_record:[…], theme_verdict, reconciliation:[…]}
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
    STATUS = [('uploaded', 'Uploaded'), ('digesting', 'Digesting'), ('digested', 'Digested'),
              ('partial', 'Partly unreadable'), ('error', 'Unreadable')]
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
    doc_role = models.CharField(max_length=20, blank=True)  # cim | model | qoe | market | structure | legal | sponsor_memo | financials | other
    role_set_by_user = models.BooleanField(default=False)
    readability = models.JSONField(default=dict, blank=True)  # local readability check at upload (extract.inspect)
    coverage = models.JSONField(default=dict, blank=True)  # {parts, ok, failed:[{label, why}], retried:[label]}
    error = models.TextField(blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)  # original deleted to free space; fact sheet kept
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']


class AnalysisJob(models.Model):
    STAGES = ['digest', 'research', 'risk', 'integrate', 'score', 'memo']
    REVISE_STAGES = ['rescore', 'revise']
    deal = models.ForeignKey(Deal, related_name='jobs', on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.QUEUED)
    stage = models.CharField(max_length=20, blank=True)
    stage_detail = models.CharField(max_length=500, blank=True)
    model = models.CharField(max_length=60, blank=True)
    digest_model = models.CharField(max_length=60, blank=True)
    framework_version = models.IntegerField(null=True, blank=True)
    allow_partial = models.BooleanField(default=False)  # deal lead chose to run despite unreadable files
    mode = models.CharField(max_length=10, default='full')  # full | revise (memo + scores from review comments only)
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


class Framework(models.Model):
    """An editable scoring framework (one per track). `config` is structured; `guidance` is free text."""
    key = models.CharField(max_length=10, primary_key=True)  # buyout | cv | vg
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    config = models.JSONField(default=dict)
    guidance = models.TextField(blank=True)
    version = models.IntegerField(default=1)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    updated_at = models.DateTimeField(auto_now=True)


class FrameworkVersion(models.Model):
    """Snapshot of every saved version, for history and restore."""
    framework = models.ForeignKey(Framework, related_name='versions', on_delete=models.CASCADE)
    version = models.IntegerField()
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    config = models.JSONField(default=dict)
    guidance = models.TextField(blank=True)
    note = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-version']
        unique_together = [('framework', 'version')]


class AppSetting(models.Model):
    """Small key/value store for team settings (model budget, storage capacity…)."""
    key = models.CharField(max_length=60, primary_key=True)
    value = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)


class MemoVersion(models.Model):
    """Every completed analysis keeps its memo, so older versions stay available — clearly dated — but never pose as the latest."""
    deal = models.ForeignKey(Deal, related_name='memos', on_delete=models.CASCADE)
    job = models.ForeignKey(AnalysisJob, null=True, blank=True, on_delete=models.SET_NULL)
    html = models.TextField()
    adcg_score = models.FloatField(null=True, blank=True)
    risk_score = models.IntegerField(null=True, blank=True)
    band = models.CharField(max_length=20, blank=True)
    model = models.CharField(max_length=60, blank=True)
    framework_version = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']


class MemoComment(models.Model):
    """A deal lead's note on the memo, captured while reading (typed or dictated). Open notes can be applied
    with a cheap 'revise' run that re-scores and rewrites only the affected sections — no new research."""
    STANCES = ['agree', 'disagree', 'context', 'question', 'change']
    deal = models.ForeignKey(Deal, related_name='comments', on_delete=models.CASCADE)
    memo = models.ForeignKey(MemoVersion, null=True, blank=True, on_delete=models.SET_NULL, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    stance = models.CharField(max_length=12, default='context')
    text = models.TextField()
    quote = models.TextField(blank=True)          # the passage selected in the memo
    section = models.CharField(max_length=200, blank=True)
    via = models.CharField(max_length=8, default='typed')   # typed | voice
    status = models.CharField(max_length=10, default='open')  # open | applied | dismissed
    applied_in = models.ForeignKey(MemoVersion, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    response = models.TextField(blank=True)       # how the revision addressed it
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

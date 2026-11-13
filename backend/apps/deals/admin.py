from django.contrib import admin

from .models import AnalysisJob, Deal, DealFile


class FileInline(admin.TabularInline):
    model = DealFile
    extra = 0
    fields = ('name', 'size', 'status', 'method', 'pages', 'uploaded_at')
    readonly_fields = fields


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ('name', 'track_resolved', 'stage', 'status', 'adcg_score', 'risk_score', 'updated_at')
    list_filter = ('stage', 'status', 'track_resolved', 'legacy')
    search_fields = ('name', 'sponsor', 'sector', 'sub_sector')
    inlines = [FileInline]


@admin.register(AnalysisJob)
class JobAdmin(admin.ModelAdmin):
    list_display = ('deal', 'status', 'stage', 'model', 'cost', 'created_at', 'finished_at')
    list_filter = ('status',)

from django.contrib import admin
from .models import (
    Level, Semester, Course, ClassSession, UserProfile,
    TAProfile, TACode, AttendanceCode, AttendanceRecord,
    SupportTicket, CodeMisuseAlert, CulturalDate, SystemNotification,
    SWASAEvent, CourseRegistration,
)


class CourseRegistrationInline(admin.TabularInline):
    model = CourseRegistration
    extra = 0
    autocomplete_fields = ('course',)
    readonly_fields = ('registered_at', 'deregistered_at', 'deregistered_by')
    fields = ('course', 'is_active', 'registered_at', 'deregistered_at', 'deregistered_by')


@admin.register(Level)
class LevelAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ('name', 'year', 'start_date', 'end_date', 'is_active', 'is_archived')
    list_filter = ('year', 'is_active', 'is_archived')
    search_fields = ('name',)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'level', 'semester', 'student_count')
    list_filter = ('level', 'semester')
    search_fields = ('code', 'name')

    @admin.display(description='Students')
    def student_count(self, obj):
        return obj.course_registrations.filter(is_active=True).count()


@admin.register(ClassSession)
class ClassSessionAdmin(admin.ModelAdmin):
    list_display = ('course', 'date', 'start_time', 'end_time', 'topic', 'lecturer')
    list_filter = ('course__level', 'course', 'date')
    search_fields = ('topic', 'course__code', 'course__name')
    ordering = ('course__code', 'date')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'level', 'student_id_number', 'student_email', 'email_verified')
    list_filter = ('level', 'email_verified')
    search_fields = ('user__username', 'student_id_number', 'student_email')
    readonly_fields = ('email_verification_token', 'verification_sent_at')
    inlines = (CourseRegistrationInline,)


@admin.register(CourseRegistration)
class CourseRegistrationAdmin(admin.ModelAdmin):
    list_display = ('user_profile', 'course', 'is_active', 'registered_at', 'deregistered_at', 'deregistered_by')
    list_filter = ('is_active', 'course__level', 'course')
    search_fields = ('user_profile__user__username', 'user_profile__student_id_number', 'course__code', 'course__name')
    readonly_fields = ('registered_at',)
    autocomplete_fields = ('user_profile', 'course', 'deregistered_by')


@admin.register(TAProfile)
class TAProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'is_approved', 'is_active', 'approved_at')
    list_filter = ('is_approved', 'is_active', 'assigned_levels')
    search_fields = ('user__username', 'user__email', 'phone_number')
    readonly_fields = ('approved_at',)
    filter_horizontal = ('assigned_levels', 'assigned_courses')
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'phone_number')
        }),
        ('Assigned Levels & Courses', {
            'fields': ('assigned_levels', 'assigned_courses')
        }),
        ('Approval Status', {
            'fields': ('is_approved', 'approved_by', 'approved_at', 'approval_notes')
        }),
        ('Account Status', {
            'fields': ('is_active',)
        }),
    )
    
    actions = ['approve_selected_tas', 'delete_ta_and_account']

    def delete_ta_and_account(self, request, queryset):
        """Fully remove selected TAs, including their underlying User account.

        Deleting a TAProfile alone leaves an orphaned User that keeps the email
        and username locked (blocking re-registration) and can still log in to a
        broken, role-less state. This action deletes the User instead, which
        cascades to the TAProfile — the correct way to remove a TA.
        """
        users = [tp.user for tp in queryset.select_related('user')]
        deleted = 0
        for user in users:
            label = user.username
            user.delete()  # cascades to the TAProfile
            deleted += 1
        self.message_user(
            request,
            f'{deleted} TA(s) fully removed, including their user account(s).'
        )
    delete_ta_and_account.short_description = "Delete TA AND their user account (frees the email)"

    def approve_selected_tas(self, request, queryset):
        """Approve the selected TAs AND email each one.

        Iterates (rather than a bulk .update()) so every newly-approved TA gets
        the approval notification — the same behaviour as the Pending-TAs page.
        """
        from django.utils import timezone
        from .views import send_ta_approval_email

        approved = 0
        emailed = 0
        for ta_profile in queryset.filter(is_approved=False):
            ta_profile.is_approved = True
            ta_profile.approved_by = request.user
            ta_profile.approved_at = timezone.now()
            ta_profile.save()
            approved += 1
            if send_ta_approval_email(ta_profile, request=request):
                emailed += 1

        self.message_user(
            request,
            f'{approved} TA(s) approved, {emailed} approval email(s) sent.'
        )
    approve_selected_tas.short_description = "Approve selected TAs (and email them)"

    def save_model(self, request, obj, form, change):
        """When an admin flips is_approved on to True via the change form,
        stamp the approver and send the approval email."""
        from django.utils import timezone
        from .views import send_ta_approval_email

        newly_approved = False
        if change and 'is_approved' in form.changed_data and obj.is_approved:
            newly_approved = True
            if not obj.approved_by:
                obj.approved_by = request.user
            if not obj.approved_at:
                obj.approved_at = timezone.now()

        super().save_model(request, obj, form, change)

        if newly_approved:
            if send_ta_approval_email(obj, request=request):
                self.message_user(request, f'Approval email sent to {obj.user.email}.')
            else:
                self.message_user(
                    request,
                    f'TA approved, but the approval email could not be sent to {obj.user.email or "(no email on file)"}.',
                    level='WARNING',
                )


@admin.register(TACode)
class TACodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'student', 'class_session', 'ta', 'is_used', 'is_distributed', 'generated_at')
    list_filter = ('is_used', 'is_distributed', 'class_session__course')
    search_fields = ('code', 'student__username', 'ta__username')


@admin.register(AttendanceCode)
class AttendanceCodeAdmin(admin.ModelAdmin):
    list_display = ('code_string', 'student', 'class_session', 'generated_at', 'expires_at', 'used_at')
    list_filter = ('class_session__course',)
    search_fields = ('code_string', 'student__username')
    readonly_fields = ('generated_at',)


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ('student', 'class_session', 'submitted_at', 'ip_address', 'status')
    list_filter = ('class_session__course', 'status')
    search_fields = ('student__username',)


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('subject', 'student', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('subject', 'student__username', 'message')


@admin.register(CodeMisuseAlert)
class CodeMisuseAlertAdmin(admin.ModelAdmin):
    list_display = ('code', 'attempted_by', 'attempted_at', 'is_resolved')
    list_filter = ('is_resolved',)
    search_fields = ('code__code_string', 'attempted_by__username')


@admin.register(CulturalDate)
class CulturalDateAdmin(admin.ModelAdmin):
    list_display = ('emoji', 'name', 'day', 'month', 'is_active', 'created_at')
    list_filter = ('is_active', 'month')
    list_editable = ('is_active',)
    ordering = ('month', 'day')
    search_fields = ('name',)
    fieldsets = (
        (None, {
            'fields': ('name', 'emoji', 'day', 'month', 'is_active'),
        }),
        ('Message', {
            'fields': ('description',),
        }),
    )


@admin.register(SystemNotification)
class SystemNotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'notification_type', 'is_read', 'created_at')
    list_filter  = ('notification_type', 'is_read')
    search_fields = ('title', 'user__username')
    readonly_fields = ('created_at', 'read_at')


@admin.register(SWASAEvent)
class SWASAEventAdmin(admin.ModelAdmin):
    list_display = ('title', 'event_type', 'event_date', 'venue', 'is_published', 'created_at')
    list_filter = ('event_type', 'event_date', 'is_published')
    list_editable = ('is_published',)
    search_fields = ('title', 'description', 'venue')
    ordering = ('-event_date',)
    # created_by is auto-set to the current admin in save_model, so it must be
    # read-only here — otherwise it's a required dropdown and leaving it blank
    # silently blocks the save ("This field is required").
    readonly_fields = ('created_at', 'created_by')
    filter_horizontal = ('target_levels',)

    def save_model(self, request, obj, form, change):
        if obj.created_by_id is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        # Runs AFTER the M2M (target_levels) is saved, so recipients can be
        # resolved. Keeps the per-user bell notifications in sync with the event:
        # creates them on publish, updates their text on edit, prunes users no
        # longer targeted, and removes them all if the event is unpublished.
        super().save_related(request, form, formsets, change)
        self._sync_notifications(request, form.instance)

    def _recipient_ids(self, event):
        from django.contrib.auth.models import User
        from django.db.models import Q
        level_ids = list(event.target_levels.values_list('id', flat=True))
        qs = User.objects.filter(is_active=True)
        if level_ids:
            qs = qs.filter(
                Q(userprofile__level_id__in=level_ids)      # students in the levels
                | Q(is_staff=True)                          # admins/lecturers see all
                | Q(taprofile__assigned_levels__id__in=level_ids)  # TAs for the levels
            )
        return set(qs.values_list('id', flat=True).distinct())

    def _sync_notifications(self, request, event):
        from django.urls import reverse

        existing = {n.user_id: n for n in SystemNotification.objects.filter(event=event)}

        if not event.is_published:
            if existing:
                SystemNotification.objects.filter(event=event).delete()
                self.message_user(request, 'Event unpublished — its notifications were removed.')
            return

        emoji = {'event': '📅', 'news': '📰', 'announcement': '📢'}.get(event.event_type, '📢')
        label = event.get_event_type_display()
        title = f"{label}: {event.title}"[:200]
        desc = event.description or ''
        message = desc if len(desc) <= 240 else desc[:237] + '…'
        link = reverse('attendance:community_events')

        recipient_ids = self._recipient_ids(event)

        # Prune users no longer targeted.
        stale = [uid for uid in existing if uid not in recipient_ids]
        if stale:
            SystemNotification.objects.filter(event=event, user_id__in=stale).delete()

        # Update content for users who already have the notification (keeps their
        # read state) so event edits are reflected.
        for uid, n in existing.items():
            if uid in recipient_ids:
                n.title, n.message, n.emoji, n.link = title, message, emoji, link
                n.save(update_fields=['title', 'message', 'emoji', 'link'])

        # Create for newly targeted users.
        new_ids = recipient_ids - set(existing)
        if new_ids:
            SystemNotification.objects.bulk_create(
                [
                    SystemNotification(
                        user_id=uid, title=title, message=message, emoji=emoji,
                        link=link, event=event,
                        notification_type=SystemNotification.TYPE_SYSTEM,
                    )
                    for uid in new_ids
                ],
                batch_size=500,
            )
        self.message_user(request, f'Notified {len(recipient_ids)} user(s) about this {label.lower()}.')
    fieldsets = (
        ('Content', {
            'fields': ('title', 'description', 'event_type', 'image_url'),
        }),
        ('Date & Location', {
            'fields': ('event_date', 'event_time', 'venue'),
        }),
        ('Audience', {
            'fields': ('target_levels',),
            'description': 'Leave empty to notify everyone. Select one or more '
                           'levels to notify only students in those levels '
                           '(admins and their TAs are always notified).',
        }),
        ('Publishing', {
            'fields': ('is_published', 'created_by', 'created_at'),
        }),
    )
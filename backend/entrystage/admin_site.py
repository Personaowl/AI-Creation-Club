from django.contrib.admin import AdminSite
from django.contrib.admin.apps import AdminConfig
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.urls import reverse


class ClubAdminSite(AdminSite):
    site_title = "AI Creation Club 作品平台"
    site_header = f"{site_title} · 管理后台"
    index_title = "管理概览"
    index_template = "admin/club_dashboard.html"

    def index(self, request, extra_context=None):
        user = request.user
        metrics = []
        if user.has_perm("works.view_work") or user.has_perm("works.change_work"):
            from works.models import Work

            counts = Work.objects.aggregate(
                pending=Count("pk", filter=Q(status=Work.Status.PENDING)),
                published=Count("pk", filter=Q(status=Work.Status.APPROVED, is_visible=True)),
            )
            work_list = reverse("admin:works_work_changelist")
            metrics.extend([
                {
                    "kind": "review",
                    "title": "待审核作品",
                    "value": counts["pending"],
                    "url": work_list + "?status__exact=pending",
                    "action": "查看审核队列",
                },
                {
                    "kind": "published",
                    "title": "已上架作品",
                    "value": counts["published"],
                    "url": work_list + "?status__exact=approved&is_visible__exact=1",
                    "action": "管理已上架作品",
                },
            ])
        if user.has_perm("auth.view_user") or user.has_perm("auth.change_user"):
            members = get_user_model().objects.filter(is_active=True, is_staff=False, is_superuser=False)
            metrics.append({
                "kind": "members",
                "title": "有效成员账号",
                "value": members.count(),
                "url": reverse("admin:auth_user_changelist"),
                "action": "管理成员账号",
            })
        return super().index(request, {
            "club_metrics": metrics,
            "can_add_member": user.has_perm("auth.add_user"),
            **(extra_context or {}),
        })


class ClubAdminConfig(AdminConfig):
    default_site = "entrystage.admin_site.ClubAdminSite"
